"""Harness-agnostic hook detectors.

Each subcommand here is content kb owns (what a failure looks like, what to say
about it), read as plain text on stdin and, on a match, printed as plain text to
stdout -- no assumption about which harness invoked it or that harness's own
event/JSON envelope. A harness's own hook mechanism (Claude Code's settings.json
PostToolUse, a different tool's equivalent) is a thin adapter around one of these:
extract this invocation's output into plain text, pipe it through the matching
`kb hooks` subcommand, and surface non-empty stdout however that harness surfaces
hook feedback. See kb instructions #18 (legacy-claude-code-artifacts) for the
same content-vs-mechanism split applied to the Instruction tree itself -- this is
that principle applied to hook wiring instead of memory content.
"""

import argparse
import os
import re
import subprocess
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

# mypy's own failure summary, e.g. "Found 6 errors in 4 files (checked 171 source files)" -- not
# ruff's "Found 3 errors.", which shares the first words.
_MYPY_FAILURE_RE = re.compile(r"Found \d+ errors? in \d+ files? \(checked \d+ source files?\)")

_MYPY_HINT = (
    "A mypy run just failed. Before reaching for cast() or another type-checker "
    "workaround, run `kb si show type-safety` for the correct-fix "
    "guidance -- a real narrowing construct (isinstance, TypeGuard, runtime assert), "
    "never cast()."
)


# `git`, then any global options (`-C DIR`, `--git-dir=...`, `-c key=value`), then the `commit`
# subcommand, starting where a command starts (a line's beginning or after a shell separator),
# so "git commit" inside another command's arguments is not one.
_GIT_COMMIT_RE = re.compile(
    r"(?:^|[;&|(])\s*git(?:\s+-[Cc]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+commit(?![\w-])", re.MULTILINE
)

_POST_COMMIT_HINT = (
    "A commit just succeeded: a piece of work is finished. Run `kb si show session-handoff` and do its pass "
    "for the work since the previous pass."
)


def cmd_post_commit_check(args: argparse.Namespace) -> None:
    """Read "<exit_code>\\n<command>" on stdin (the Bash tool's own exit code, then the
    command string); if the command was a `git commit` and it exited 0, print a reminder
    to run the session-handoff pass. Prints nothing (exit 0) otherwise, so a
    harness adapter can pipe any Bash command through unconditionally and only act on
    non-empty output."""
    exit_code, _, command = sys.stdin.read().partition("\n")
    if exit_code.strip() == "0" and _GIT_COMMIT_RE.search(command):
        print(_POST_COMMIT_HINT)


def cmd_mypy_check(args: argparse.Namespace) -> None:
    """Read command output on stdin; if it looks like a failed mypy run, print a
    reminder to stdout. Prints nothing (exit 0) otherwise, so a harness adapter
    can pipe any command's output through unconditionally and only act on
    non-empty output."""
    output = sys.stdin.read()
    if _MYPY_FAILURE_RE.search(output):
        print(_MYPY_HINT)


_FIND_ROOT_RE = re.compile(r"(?<![\w./])find\s+/(?:\s|$)")

_FIND_ROOT_HINT = (
    "Blocked: `find /` (or `find / ...`) searches the entire filesystem from root -- "
    "almost never intended and can exhaust system resources on large trees. Scope the "
    "search to a specific directory instead, e.g. `find . -name ...` or `find /home/user/project -name ...`."
)


def cmd_find_root_check(args: argparse.Namespace) -> None:
    """Read a Bash command string on stdin; if it's a `find` invocation rooted at
    literal `/` (not a subdirectory like `/home/...`), print a block reason to stdout.
    Prints nothing (exit 0) otherwise, so a harness adapter can pipe any Bash command
    through unconditionally and only block on non-empty output."""
    command = sys.stdin.read()
    if _FIND_ROOT_RE.search(command):
        print(_FIND_ROOT_HINT)


_PKILL_RE = re.compile(r"(?<![\w./])pkill(?:\s|$)")

_PKILL_HINT = (
    "Blocked: `pkill` matches and kills processes by name/pattern across the whole system -- "
    "easy to hit an unintended process (another user's, another project's) since it isn't scoped "
    "to a specific PID. Use `kill PID` with a PID confirmed via `pgrep`/`ps` first, or scope more "
    "narrowly (e.g. `pkill -f` with a precise, tested pattern) only when a PID-based kill genuinely "
    "isn't workable."
)


def cmd_pkill_check(args: argparse.Namespace) -> None:
    """Read a Bash command string on stdin; if it invokes `pkill`, print a block reason
    to stdout. Prints nothing (exit 0) otherwise, so a harness adapter can pipe any Bash
    command through unconditionally and only block on non-empty output."""
    command = sys.stdin.read()
    if _PKILL_RE.search(command):
        print(_PKILL_HINT)


_GIT_ADD_A_RE = re.compile(r"(?<![\w.-])git\s+add\s+(?:.*\s)?(?:-A|--all|-\.)(?:\s|$)")

_GIT_ADD_A_HINT = (
    "Blocked: `git add -A` (or `--all`) stages every change in the working tree, including "
    "untracked files that may be accidental or generated rather than real project sources -- "
    "review `git status` and stage specific paths instead, e.g. `git add path/to/file.py`."
)


def cmd_git_add_a_check(args: argparse.Namespace) -> None:
    """Read a Bash command string on stdin; if it's a `git add` invocation using -A/--all
    (whole-tree staging), print a block reason to stdout. Prints nothing (exit 0) otherwise,
    so a harness adapter can pipe any Bash command through unconditionally and only block on
    non-empty output."""
    command = sys.stdin.read()
    if _GIT_ADD_A_RE.search(command):
        print(_GIT_ADD_A_HINT)


_MEMORY_MD_RE = re.compile(r"(?:^|/)\.claude/(?:memory|projects/[^/]+/memory)/.*\.md$")

_MEMORY_MD_HINT = (
    "Blocked: writing to a Claude Code memory file (~/.claude/memory/*.md or "
    "~/.claude/projects/<project>/memory/*.md). Durable content belongs in the kb "
    "Instruction tree instead -- run `kb instructions show 18` (legacy-claude-code-artifacts) "
    "for the content-vs-mechanism split. The only exception is content genuinely about the "
    "collaboration itself (a correction, a confirmed approach, a user preference) -- even "
    "then, ask before writing rather than writing directly."
)


def cmd_memory_md_check(args: argparse.Namespace) -> None:
    """Read a file path on stdin (the target of a Write/Edit call); if it's a Claude Code
    memory file (~/.claude/memory/*.md or the per-project ~/.claude/projects/<hash>/memory/*.md
    form), print a block reason to stdout. Prints nothing (exit 0) otherwise, so a harness
    adapter can pipe any file-write target through unconditionally and only block on
    non-empty output."""
    path = sys.stdin.read().strip()
    if _MEMORY_MD_RE.search(path):
        print(_MEMORY_MD_HINT)


_PLAN_MD_RE = re.compile(r"(?:^|/)\.claude/plans/.*\.md$")

_PLAN_MD_HINT = (
    "Reminder: this Claude Code plan file (~/.claude/plans/*.md) is a required part of the "
    "plan-mode mechanism (ExitPlanMode reads it), so it can't be blocked outright the way "
    "~/.claude/memory/*.md is -- but its CONTENT is not durable, it vanishes with the session. "
    "Same content-vs-mechanism split as `kb instructions show 18` (legacy-claude-code-artifacts): "
    "before or immediately after exiting plan mode, fold the actual plan detail into a kb Goal "
    "(with full detail in a Journal entry) and keep this file itself as thin as the mechanism "
    "requires -- a summary and a pointer to the kb Goal ID, not the durable copy."
)


def cmd_plan_md_check(args: argparse.Namespace) -> None:
    """Read a file path on stdin (the target of a Write/Edit call); if it's a Claude Code
    plan-mode file (~/.claude/plans/*.md), print an advisory reminder to stdout -- unlike
    memory-md-check, this is never a block, since writing this exact path is how plan mode's
    own ExitPlanMode mechanism works. Prints nothing (exit 0) otherwise, so a harness adapter
    can pipe any file-write target through unconditionally and only act on non-empty output."""
    path = sys.stdin.read().strip()
    if _PLAN_MD_RE.search(path):
        print(_PLAN_MD_HINT)


_DEPENDENCY_INSTALL_RE = re.compile(
    r"(?:^|[;&|]\s*)"
    r"(?:\w+=\S+\s+)*"  # skip leading env-var assignments (e.g. AUDITED=note215 npm install ...)
    r"(?:npm\s+(?:install|i|add)|"
    r"pnpm\s+(?:install|i|add)|"
    r"yarn\s+add|"
    r"pip3?\s+install|"
    r"uv\s+(?:add|pip\s+install)|"
    r"cargo\s+add|"
    r"gem\s+install|"
    r"go\s+get)"
    r"\s+\S"  # require at least one argument -- bare `npm install` (no target) installs the existing lockfile, not a new dependency
)

_AUDITED_RE = re.compile(r"\bAUDITED=(\S+)")

_DEPENDENCY_INSTALL_BLOCK = (
    "Blocked: this looks like it adds a new third-party dependency. Per kb instructions #27 "
    "(security), audit its supply-chain provenance BEFORE installing -- maintainer identity, "
    "release history, real adoption, lookalike/typosquat check, transitive dependency graph. "
    "Once the audit is done, write it to a kb Note (`kb notes add ...`) and re-run the same "
    "install command prefixed with AUDITED=noteN (N = that Note's id), e.g. "
    "`AUDITED=note215 npm install react-router-dom` -- this logs and links the install to its "
    "audit record for later verification, and lets the command through."
)


def cmd_dependency_install_check(args: argparse.Namespace) -> None:
    """Read a Bash command string on stdin; if it looks like it installs a new third-party
    dependency (npm/pnpm/yarn install|add, pip/uv install|add, cargo add, gem install, go get
    -- with at least one argument, so a bare `npm install` that just replays the lockfile
    doesn't match), require an `AUDITED=noteN` token in the same command line before letting
    it through. Missing the token: print a block reason to stdout (harness adapter denies the
    tool call). Token present: log a LogEntry linking this exact install command to the named
    Note (the audit record) via `kb link add`, so the audit-then-install claim is independently
    checkable later rather than a bare self-report -- then print nothing so the command proceeds.
    See kb instructions #27 (security) for the audit checklist itself."""
    command = sys.stdin.read()
    if not _DEPENDENCY_INSTALL_RE.search(command):
        return

    audited_match = _AUDITED_RE.search(command)
    if not audited_match:
        print(_DEPENDENCY_INSTALL_BLOCK)
        return

    from models.knowledge.log_entry import LogEntry
    from models.knowledge.note import Note
    from models.links.entity_link import EntityLink

    token = audited_match.group(1)
    note_match = re.fullmatch(r"note(\d+)", token, re.IGNORECASE)
    if not note_match:
        print(
            f"Blocked: AUDITED={token} doesn't match the expected `noteN` shape "
            "(e.g. AUDITED=note215) -- can't link it to an audit record."
        )
        return

    note_id = int(note_match.group(1))
    note = args.session.get(Note, note_id)
    if note is None:
        print(f"Blocked: AUDITED={token} -- no Note #{note_id} exists. Write the audit to a real Note first.")
        return

    entry = LogEntry.create(
        args.session, f"Dependency install (audited via Note #{note_id}): {command.strip()}", context=note.context
    )
    args.session.flush()
    EntityLink.create(args.session, "LogEntry", entry.id, "Note", note_id, "audited-by")
    args.session.commit()


_UV_SYNC_RE = re.compile(r"(?<![\w.-])uv\s+sync\b")

_UV_SYNC_HINT = (
    "Blocked: `uv sync` rebuilds the venv strictly from pyproject.toml/uv.lock -- any locally "
    "installed package not declared there is silently removed. In ~/kb specifically, "
    "`cli_instrumentation` is an optional, not-yet-public dependency installed this way "
    "(see pyproject.toml's mypy override and kb_cli/stats.py's import-guard comment) and is NOT "
    "listed as a project dependency -- a bare `uv sync` here destructively uninstalls it, which "
    "already happened once and cost 5 weeks of cli_instrumentation data. Before running `uv sync` "
    "in ~/kb: confirm cli_instrumentation is reinstalled afterward (reinstall it from wherever its "
    "source lives), or run `uv sync --inexact` or `uv sync --no-sources`-style scoping to avoid "
    "clobbering locally-installed-but-undeclared packages, if that fits the actual need. Re-run "
    "with `UV_SYNC_CONFIRMED=1` prefixed once this has been accounted for."
)


def cmd_uv_sync_check(args: argparse.Namespace) -> None:
    """Read a Bash command string on stdin; if it invokes `uv sync` inside ~/kb (cwd piped as
    the second stdin line, "<command>\\n<cwd>") without a UV_SYNC_CONFIRMED=1 env-var prefix,
    print a block reason to stdout -- `uv sync` reconciles the venv strictly against
    pyproject.toml/uv.lock, silently removing any locally installed package not declared there.
    ~/kb installs the optional `cli_instrumentation` package exactly this way (not a declared
    dependency), and a bare `uv sync` there once destroyed 5 weeks of its recorded data. Prints
    nothing (exit 0) otherwise, so a harness adapter can pipe any Bash command through
    unconditionally and only block on non-empty output."""
    command, _, cwd = sys.stdin.read().partition("\n")
    if not _UV_SYNC_RE.search(command):
        return
    if "UV_SYNC_CONFIRMED=1" in command:
        return
    if "/kb" not in cwd and "/kb" not in command:
        return
    print(_UV_SYNC_HINT)


_TREE_REMINDER = (
    "Re-check the Instruction tree for a child relevant to what you're about to do now, "
    "e.g. `kb si show engineering code-level-implementation`."
)

_TREE_FRONTIER_REMINDER = (
    "Unopened children of the Instruction-tree nodes this session has read: {titles}. "
    "Open (`kb si show TITLE`) any that bears on what you're about to do now."
)


def _session_si_reads(session: Session) -> Optional[set[str]]:
    """The ids (zero-padded, as in si_files) of every system instruction node this agent
    session has read with `kb si show`, or None when no registered agent session is
    detectable."""
    from kb_cli.required_reading import session_reads

    read = session_reads(session, "SiNode")
    return None if read is None else {f"{entity_id:04d}" for entity_id in read}


def _tree_reminder_text(session: Session) -> str:
    """The frontier of the system instruction tree for this agent session: the titles of
    every node whose parent the session has read with `kb si show` and which it has not read
    itself. Titles only, since each child's trigger is already in context from its parent's
    `show` output. Falls back to the generic reminder when no session is detectable or the
    session has not read the root yet, and is empty once every reachable node is read."""
    from kb_cli import si_files

    read = _session_si_reads(session)
    root = si_files.resolve("root")
    if read is None or root is None or root.id not in read:
        return _TREE_REMINDER
    frontier = si_files.unexpanded_children(read)
    if not frontier:
        return ""
    return _TREE_FRONTIER_REMINDER.format(titles=", ".join(node.title for node in frontier))


_UNREAD_NODE_HINT = "Blocked: this session has not read the {purpose}. Run `kb si show {title}`, then retry."


def _unread_node_hint(session: Session, title: str, purpose: str) -> Optional[str]:
    """A block reason if this agent session has not read the system instruction node
    `title`; None when it has, when no agent session is detectable (no reads are recorded to
    check against), or when the node does not exist."""
    from kb_cli import si_files

    node = si_files.resolve(title)
    read = _session_si_reads(session)
    if node is None or read is None or node.id in read:
        return None
    return _UNREAD_NODE_HINT.format(purpose=purpose, title=node.title)


def cmd_commit_check(args: argparse.Namespace) -> None:
    """Read a Bash command on stdin; if it runs `git commit` in an agent session that has not
    read the commit-messages system instruction node, print a block reason to stdout."""
    if not _GIT_COMMIT_RE.search(sys.stdin.read()):
        return
    hint = _unread_node_hint(args.session, "commit-messages", "commit-message rules")
    if hint:
        print(hint)


# A kb command that writes a record body. Markdown files are gated by required-reading-check,
# through the documentation node's write-globs.
_DOC_COMMAND_RE = re.compile(
    r"\bkb\s+(?:notes?|todo|bug|goal|journal|win|idea|log|inbox|wishlist|si|i|instructions)\s+(?:add|update|edit)\b",
    re.IGNORECASE,
)


def _doc_hint(session: Session) -> Optional[str]:
    return _unread_node_hint(session, "documentation", "documentation guidance")


# The --file target of a `text sub`/`text replace` edit of a Python file.
_TEXT_EDIT_PY_RE = re.compile(r"\btext\s+(?:sub|replace)\b[^\n|;&]*--file\s+(\S+\.py)\b")


def _black_project(path: Path) -> Optional[Path]:
    """The nearest directory above `path` whose pyproject.toml configures black, or None."""
    for parent in path.resolve().parents:
        pyproject = parent / "pyproject.toml"
        if pyproject.is_file():
            return parent if "[tool.black]" in pyproject.read_text() else None
    return None


def _black_exclusions(project: Path) -> Optional[str]:
    """The project's black exclude patterns combined into one regex, or None. black applies
    exclude/extend-exclude only while scanning directories, so a file passed by path is
    formatted even when excluded unless the patterns are passed again as --force-exclude."""
    config = tomllib.loads((project / "pyproject.toml").read_text()).get("tool", {}).get("black", {})
    patterns = [config[key] for key in ("exclude", "extend-exclude", "force-exclude") if config.get(key)]
    return "|".join(f"(?:{p})" for p in patterns) or None


def cmd_format_python(args: argparse.Namespace) -> None:
    """Format each Python file named on stdin with black, when its project configures black
    (a [tool.black] section in the nearest pyproject.toml), so a commit-time `black --check`
    finds nothing to reformat. stdin holds one path per line, or with --command a Bash
    command whose `text sub`/`text replace --file X.py` targets are formatted. Prints what it
    reformatted; silent otherwise."""
    text = sys.stdin.read()
    paths = _TEXT_EDIT_PY_RE.findall(text) if args.command else text.splitlines()
    for raw in paths:
        path = Path(raw.strip())
        if path.suffix != ".py" or not path.is_file():
            continue
        project = _black_project(path)
        if project is None:
            continue
        command = ["uv", "run", "--project", str(project), "black", str(path)]
        exclusions = _black_exclusions(project)
        if exclusions:
            command += ["--force-exclude", exclusions]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0 and "reformatted" in result.stderr:
            print(f"black reformatted {path}")


_REQUIRED_READING_HINT = "Blocked: writing {path} requires reading first: {commands}. Run them, then retry."


def cmd_required_reading_check(args: argparse.Namespace) -> None:
    """Read a file path on stdin (the target of a Write/Edit call), or with --command a Bash
    command whose file writes are taken from its text; for each, if instruction nodes whose
    write-globs match it are unread in this agent session, print a block reason naming them."""
    from kb_cli.required_reading import command_targets, unread_for

    text = sys.stdin.read()
    paths = command_targets(text) if args.command else [text.strip()]
    for path in paths:
        commands = unread_for(args.session, path)
        if commands:
            print(_REQUIRED_READING_HINT.format(path=path, commands=", ".join(f"`{c}`" for c in commands)))
            return


def cmd_doc_command_check(args: argparse.Namespace) -> None:
    """Read a Bash command on stdin; if it writes a kb record body and this agent session has
    not read the documentation system instruction node, print a block reason to stdout."""
    if not _DOC_COMMAND_RE.search(sys.stdin.read()):
        return
    hint = _doc_hint(args.session)
    if hint:
        print(hint)


_ARCHIVE_REMINDER = (
    "A web search/fetch just ran. If anything in the results actually panned out as useful or worth keeping "
    "(not the bulk of low-quality/SEO/irrelevant hits a search normally returns), snapshot it now: "
    "`kb ab add URL TITLE REASON`. Judgment call each time, not an auto-save -- most search results aren't worth it."
)


def cmd_archive_reminder(args: argparse.Namespace) -> None:
    """Unconditional -- always prints the same short reminder, no stdin/detection needed.
    Deliberately does not auto-save anything: a WebSearch/WebFetch turns up mostly
    low-quality/SEO/irrelevant results, so saving every URL a search touches would hoover up
    the internet (the exact failure mode kb Todo #70 calls out avoiding). This only nudges a
    judgment call at the moment it's cheapest to make -- right after seeing the results -- and
    leaves the actual save-or-skip decision to whoever's driving, the same as any other
    `kb ab add` call."""
    print(_ARCHIVE_REMINDER)


_LAST_ACTIVITY_FILE = Path("/dev/shm/kb-last-activity")


def cmd_tree_reminder(args: argparse.Namespace) -> None:
    """Prints, on every prompt, the titles of the instruction-tree nodes this session can
    reach but has not opened (see _tree_reminder_text), plus the current time. Deterministic
    backstop for kb Goal #23's finding that per-node triggers don't reliably fire mid-task
    from root's own wording alone (root is read once, at the first tool call of a session,
    with no built-in re-entry point when a new sub-situation arises later). Listing only the
    unopened frontier, by title, keeps it to a few hundred bytes: Goal #23's Journal rejected
    the full per-topic checklist as too costly to inject before every single response.

    Also stamps _LAST_ACTIVITY_FILE with the current time on every call -- since this fires
    on every UserPromptSubmit across every session (not just one), it's the natural shared
    heartbeat for cmd_daily_check's sleep-detection, without needing a dedicated hook of its
    own."""
    _LAST_ACTIVITY_FILE.write_text(str(time.time()))
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    text = _tree_reminder_text(args.session)
    print(f"{text} [{timestamp}]" if text else f"[{timestamp}]")


_DAILY_CHECK_LOCK = Path("/dev/shm/kb-daily-check.lock")
_DAILY_CHECK_SLEEP_SECONDS = 8 * 60 * 60  # no activity in ANY session for this long implies the user slept

_DAILY_CHECK_PRIME = (
    "This is today's first new Claude Code session (the daily-check lock was free) -- "
    "start with the daily kb routine: run `kb summary` and `todo pending`, and work "
    "through anything urgent/due before moving to other work this session. Once the "
    "daily routine is handled, no need to keep coming back to it -- the lock stays held "
    "for every other session opened today. To hand the daily-check slot to a different "
    "session instead (e.g. this one turned out to be the wrong one to prime), run "
    "`kb hooks daily-check-release`."
)

# kb ships to users who don't necessarily have any particular other tool installed, so a
# site-specific addition to the daily routine (e.g. a local caldav-cli) is never hardcoded
# here -- it's appended only if KB_DAILY_CHECK_EXTRA is set in the environment, which a given
# install's own shell profile is responsible for setting, not kb itself. See
# docs/daily-check.md for details.


def cmd_daily_check(args: argparse.Namespace) -> None:
    """Read a session ID on stdin -- this is the harness-agnostic path real hook wiring
    uses (e.g. Claude Code's settings.json piping `.session_id` from the SessionStart
    JSON envelope), and stays correct for any harness regardless of how that harness
    exposes its own session ID. If stdin is empty (e.g. a bare manual invocation, not
    piped), fall back to the CLAUDE_CODE_SESSION_ID env var as a convenience -- this
    fallback is Claude-Code-specific and only ever a manual-testing nicety, never relied
    on by the real settings.json wiring above, which always pipes stdin explicitly.

    If a lockfile already claims today's daily-check slot for a different session, print
    nothing (business as usual) -- UNLESS _LAST_ACTIVITY_FILE (stamped by
    cmd_tree_reminder on every UserPromptSubmit, across every session) shows no activity
    anywhere for _DAILY_CHECK_SLEEP_SECONDS, which is treated as "the user slept" and
    frees the lock regardless of which session holds it. This deliberately doesn't
    hard-code a midnight boundary -- a genuine multi-hour gap in activity is the actual
    signal, not a calendar-day rollover, so a late-night-into-early-morning session
    correctly keeps the same lock instead of being treated as a new day. Reboot also
    clears the lock (tmpfs), matching that sessions here never span a reboot (always
    /kb-persist + a fresh session next time)."""
    session_id = sys.stdin.read().strip()
    if not session_id:
        session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if not session_id:
        print(
            "kb hooks daily-check: no session ID on stdin or in CLAUDE_CODE_SESSION_ID, doing nothing",
            file=sys.stderr,
        )
        return
    if _DAILY_CHECK_LOCK.exists():
        holder = _DAILY_CHECK_LOCK.read_text().strip()
        idle: float = _DAILY_CHECK_SLEEP_SECONDS
        if _LAST_ACTIVITY_FILE.exists():
            idle = time.time() - float(_LAST_ACTIVITY_FILE.read_text().strip())
        if holder != session_id and idle < _DAILY_CHECK_SLEEP_SECONDS:
            return
    _DAILY_CHECK_LOCK.write_text(session_id)
    prime = _DAILY_CHECK_PRIME
    extra = os.environ.get("KB_DAILY_CHECK_EXTRA", "").strip()
    if extra:
        prime += " " + extra
    print(prime)


def cmd_session_register(args: argparse.Namespace) -> None:
    """Read a session ID on stdin (SessionStart's own JSON envelope's .session_id, matching
    daily-check's convention), falling back to current_session_id() for manual testing.
    Registers/refreshes this session as live -- see HarnessSession.register (models/agents/harness_session.py) and
    kb Goal #46 for the full cross-session-messaging design this feeds. Title is left unset
    here (SessionStart's envelope doesn't carry a resolved title yet); `kb sessions list`
    reads whatever HarnessSession.title holds, empty until something else backfills it."""
    from harness import current_session_id
    from models.agents.harness_session import HarnessSession

    from kb_cli.sessions import _find_claude_ancestor_pid

    session_id = sys.stdin.read().strip()
    if not session_id:
        session_id = current_session_id() or ""
    if not session_id:
        return
    HarnessSession.register(
        args.session,
        session_id,
        cwd=os.getcwd(),
        pid=_find_claude_ancestor_pid(),
        reports_permission_prompts=args.reports_permission_prompts,
    )
    args.session.commit()


def cmd_session_inbox_check(args: argparse.Namespace) -> None:
    """Layer 1 of kb Goal #46's cross-session messaging delivery: called from
    UserPromptSubmit on every prompt, prints any of this session's unread SessionMessages
    (marking them read). `kb sessions listen` (Layer 2, proactive delivery) is opt-in, not
    started or nagged-for by default -- forcing it onto every session proved too heavyweight
    once kb had more than one user (see CLAUDE_GLOBAL.md's own history and kb Goal #23/#46).
    A session that never runs Layer 2 simply only sees messages via this per-prompt check,
    which is an acceptable degraded mode, not an error state to nag about.

    Also reopens this session if it is marked ended: see the comment at that step."""
    from models.base import _now
    from harness import current_session_id
    from models.agents.channel import ChannelMessage, ChannelRead
    from models.agents.harness_session import HarnessSession, HarnessSessionStatus

    from kb_cli.sessions import _find_claude_ancestor_pid

    session_id = current_session_id()
    if not session_id:
        return
    row = HarnessSession.by_harness_id(args.session, session_id)
    if row is None:
        return
    if row.ended_at is not None:
        # A prompt in this session proves it is live, which outranks any inference that
        # marked it ended (e.g. a liveness read that raced a migration).
        row = HarnessSession.register(args.session, session_id, cwd=os.getcwd(), pid=_find_claude_ancestor_pid())
    row.status = HarnessSessionStatus.INFERRING
    row.last_active_at = _now()
    # A prompt is delivered only between tool calls, never while a permission dialog is open.
    row.awaiting_permission = False
    args.session.commit()
    messages = ChannelMessage.unread(args.session, row.id)
    lines = [f"New message from session {msg.sender.harness_id}:\n  {msg.body}" for msg in messages]
    channel_ids = {msg.channel_id for msg in messages}
    for channel_id in channel_ids:
        ChannelRead.record(args.session, channel_id=channel_id, session_id=row.id)
    if messages:
        args.session.commit()

    if lines:
        print("\n\n".join(lines))


def cmd_session_stop(args: argparse.Namespace) -> None:
    """Called from the Stop hook -- marks this session IDLE and bumps last_response_at.
    Silent always (no stdout), this only updates HarnessSession bookkeeping for kb sessions
    list to show honest live-status info, per kb Goal #46's design discussion."""
    from models.base import _now
    from harness import current_session_id
    from models.agents.harness_session import HarnessSession, HarnessSessionStatus

    session_id = current_session_id()
    if not session_id:
        return
    row = HarnessSession.by_harness_id(args.session, session_id)
    if row is None:
        return
    row.status = HarnessSessionStatus.IDLE
    row.last_response_at = _now()
    row.awaiting_permission = False
    args.session.commit()


def cmd_permission_request(args: argparse.Namespace) -> None:
    """Called from the PermissionRequest hook, which runs before Claude Code shows a permission
    dialog: marks this session as possibly showing one, so the web UI does not submit a prompt
    into it. Silent, so the dialog proceeds as usual. See HarnessSession.awaiting_permission."""
    from harness import current_session_id
    from models.agents.harness_session import HarnessSession

    session_id = current_session_id()
    if not session_id:
        return
    row = HarnessSession.by_harness_id(args.session, session_id)
    if row is None:
        return
    row.awaiting_permission = True
    args.session.commit()


def cmd_daily_check_release(args: argparse.Namespace) -> None:
    """Drop today's daily-check lock, if held, so the next new session claims it
    instead of waiting for a reboot to free it up."""
    _DAILY_CHECK_LOCK.unlink(missing_ok=True)
    print("Daily-check lock released.")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "hooks", help="Harness-agnostic hook detectors -- read command output on stdin, print a reminder on a match"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mypy = sub.add_parser(
        "mypy-check", help="Detect a failed mypy run on stdin; print a type-safety reminder if it matches"
    )
    p_mypy.set_defaults(func=cmd_mypy_check)

    p_post_commit = sub.add_parser(
        "post-commit-check",
        help='Detect a successful `git commit` ("<exit_code>\\n<command>" on stdin); '
        "print a session-handoff reminder if it matches",
    )
    p_post_commit.set_defaults(func=cmd_post_commit_check)

    p_find_root = sub.add_parser(
        "find-root-check",
        help="Detect a `find /` (root-scoped) command on stdin; print a block reason if it matches",
    )
    p_find_root.set_defaults(func=cmd_find_root_check)

    p_commit = sub.add_parser(
        "commit-check",
        help="Detect `git commit` on stdin; print a block reason if this session has not read the commit-messages node",
    )
    p_commit.set_defaults(func=cmd_commit_check)

    p_format = sub.add_parser(
        "format-python",
        help="Format Python files named on stdin with black, when their project configures it",
    )
    p_format.add_argument(
        "--command",
        action="store_true",
        help="stdin is a Bash command; format its `text sub|replace --file X.py` targets",
    )
    p_format.set_defaults(func=cmd_format_python)

    p_required = sub.add_parser(
        "required-reading-check",
        help="Read a written file path on stdin (or a Bash command with --command); block until every "
        "instruction node whose write-globs match it is read",
    )
    p_required.add_argument(
        "--command", action="store_true", help="stdin is a Bash command; check the files its text writes"
    )
    p_required.set_defaults(func=cmd_required_reading_check)

    p_doc_command = sub.add_parser(
        "doc-command-check",
        help="Detect a kb record-body write in a Bash command on stdin; block until the documentation node is read",
    )
    p_doc_command.set_defaults(func=cmd_doc_command_check)

    p_git_add_a = sub.add_parser(
        "git-add-a-check",
        help="Detect `git add -A`/`--all` on stdin; print a block reason if it matches",
    )
    p_git_add_a.set_defaults(func=cmd_git_add_a_check)

    p_pkill = sub.add_parser(
        "pkill-check",
        help="Detect a `pkill` invocation on stdin; print a block reason if it matches",
    )
    p_pkill.set_defaults(func=cmd_pkill_check)

    p_dep_install = sub.add_parser(
        "dependency-install-check",
        help="Detect a new-dependency install command on stdin; require AUDITED=noteN or print a block reason",
    )
    p_dep_install.set_defaults(func=cmd_dependency_install_check)

    p_uv_sync = sub.add_parser(
        "uv-sync-check",
        help='Detect a naive `uv sync` in ~/kb on stdin ("<command>\\n<cwd>"); print a block reason if it matches',
    )
    p_uv_sync.set_defaults(func=cmd_uv_sync_check)

    p_memory_md = sub.add_parser(
        "memory-md-check",
        help="Detect a write targeting ~/.claude/memory/*.md on stdin; print a block reason if it matches",
    )
    p_memory_md.set_defaults(func=cmd_memory_md_check)

    p_plan_md = sub.add_parser(
        "plan-md-check",
        help="Detect a write targeting ~/.claude/plans/*.md on stdin; print an advisory (non-blocking) reminder if it matches",
    )
    p_plan_md.set_defaults(func=cmd_plan_md_check)

    p_tree = sub.add_parser(
        "tree-reminder",
        help="Remind the session of the Instruction-tree nodes it can reach but has not opened",
    )
    p_tree.set_defaults(func=cmd_tree_reminder)

    p_archive = sub.add_parser(
        "archive-reminder",
        help="Unconditional one-line reminder to snapshot anything worth keeping after a WebSearch/WebFetch",
    )
    p_archive.set_defaults(func=cmd_archive_reminder)

    p_daily = sub.add_parser(
        "daily-check",
        help="Claim today's daily-check slot for this session ID (read on stdin, or CLAUDE_CODE_SESSION_ID if stdin is empty); print the priming reminder on a fresh claim, nothing if another session already holds it",
    )
    p_daily.set_defaults(func=cmd_daily_check)

    p_daily_release = sub.add_parser(
        "daily-check-release",
        help="Release today's daily-check lock so the next new session claims it",
    )
    p_daily_release.set_defaults(func=cmd_daily_check_release)

    p_session_register = sub.add_parser(
        "session-register",
        help="Register/refresh this session as live (session ID read on stdin, or current_session_id() if stdin is empty) -- see kb Goal #46",
    )
    p_session_register.add_argument(
        "--reports-permission-prompts",
        action="store_true",
        help="This harness also runs `kb hooks permission-request`, so the web UI may send prompts mid-turn",
    )
    p_session_register.set_defaults(func=cmd_session_register)

    p_session_inbox = sub.add_parser(
        "session-inbox-check",
        help="Print and mark-read this session's new SessionMessages, if any -- see kb Goal #46",
    )
    p_session_inbox.set_defaults(func=cmd_session_inbox_check)

    p_session_stop = sub.add_parser(
        "session-stop",
        help="Mark this session IDLE and bump last_response_at -- see kb Goal #46",
    )
    p_session_stop.set_defaults(func=cmd_session_stop)

    p_permission_request = sub.add_parser(
        "permission-request",
        help="Mark this session as possibly showing a permission dialog, so the web UI holds prompts",
    )
    p_permission_request.set_defaults(func=cmd_permission_request)
