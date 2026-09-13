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
import sys
import time
from pathlib import Path

_MYPY_FAILURE_RE = re.compile(r"Found \d+ error")

_MYPY_HINT = (
    "A mypy run just failed. Before reaching for cast() or another type-checker "
    "workaround, run `kb instructions show 20` (type-safety) for the correct-fix "
    "guidance -- a real narrowing construct (isinstance, TypeGuard, runtime assert), "
    "never cast()."
)


_GIT_COMMIT_RE = re.compile(r"(?<![\w.-])git\s+(?:[^&|;]*\s)?commit(?:\s|$)")

_POST_COMMIT_HINT = (
    "A commit just succeeded. Run `kb i show claude-code-session-persistence-review` and follow it now -- "
    "committing is part of that pass, not a separate step, and it must run after every successful commit."
)


def cmd_post_commit_check(args: argparse.Namespace) -> None:
    """Read "<exit_code>\\n<command>" on stdin (the Bash tool's own exit code, then the
    command string); if the command was a `git commit` and it exited 0, print a reminder
    to run the session-persistence-review pass. Prints nothing (exit 0) otherwise, so a
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

    from models import EntityLink, LogEntry, Note

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

    entry = LogEntry.create(args.session, f"Dependency install (audited via Note #{note_id}): {command.strip()}")
    args.session.flush()
    EntityLink.create(args.session, "LogEntry", entry.id, "Note", note_id, "audited-by")
    args.session.commit()


_HEREDOC_BODY_RE = re.compile(r"<<-?\s*'?(\w+)'?.*?\n.*?\n\1\b", re.DOTALL)
_QUOTED_STRING_RE = re.compile(r"'[^']*'|\"[^\"]*\"")

# Requires nohup/setsid to sit immediately before the invocation (an optional env-var prefix,
# e.g. `nohup kb sessions listen`, matching dependency-install-check's own env-var-skip
# pattern), or a trailing `&`/`disown` immediately after -- not mere co-occurrence anywhere in
# the command string, so a heredoc body or quoted string that only *mentions* the pattern in
# prose (e.g. a `kb journal add` call documenting this exact bug) doesn't false-positive.
_SESSIONS_LISTEN_BACKGROUNDED_RE = re.compile(
    r"(?:(?<![\w.-])(?:nohup|setsid)\s+(?:\w+=\S+\s+)*(?:\S*/)?kb\s+sessions\s+listen\b"
    r"|(?<![\w.-])(?:\S*/)?kb\s+sessions\s+listen\b[^\n;|]*(?:&\s*(?:[;&|]|$)|;\s*disown\b))"
)

_SESSIONS_LISTEN_SHELL_BACKGROUND_BLOCK = (
    "Blocked: this backgrounds `kb sessions listen` at the shell level (nohup/setsid/disown/trailing `&`). "
    "A shell-backgrounded process cannot deliver its result back into this conversation. Run it as its own "
    "Bash tool call using the tool's own run_in_background parameter instead: "
    'Bash({ command: "kb sessions listen", run_in_background: true }).'
)


def cmd_sessions_listen_check(args: argparse.Namespace) -> None:
    """Read a Bash command string on stdin; if it invokes `kb sessions listen` with shell-level
    backgrounding (nohup/setsid immediately prefixed, or a trailing `&`/`; disown` immediately
    after the invocation itself), print a block reason to stdout -- shell-backgrounded output
    can't be delivered back into the conversation, only the Bash tool's own run_in_background
    parameter can. Heredoc bodies and quoted strings are stripped before matching, so a command
    that merely quotes or documents the bad pattern as text (e.g. a `kb journal add`/`kb notes
    add` call about this exact detector) doesn't false-positive. Prints nothing (exit 0)
    otherwise, so a harness adapter can pipe any Bash command through unconditionally and only
    block on non-empty output."""
    command = sys.stdin.read()
    scannable = _HEREDOC_BODY_RE.sub("", command)
    scannable = _QUOTED_STRING_RE.sub("", scannable)
    if _SESSIONS_LISTEN_BACKGROUNDED_RE.search(scannable):
        print(_SESSIONS_LISTEN_SHELL_BACKGROUND_BLOCK)


_TREE_REMINDER = (
    "Re-check the Instruction tree for a child relevant to what you're about to do now, "
    "e.g. `kb si show engineering code-level-implementation`."
)


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
    """Unconditional -- always prints the same short reminder, no stdin/detection needed.
    Deterministic backstop for kb Goal #23's finding that per-node triggers don't reliably
    fire mid-task from root's own wording alone (root is read once, at the first tool call
    of a session, with no built-in re-entry point when a new sub-situation arises later).
    Kept to one line by design: Goal #23's Journal explicitly rejected a longer per-topic
    checklist as too costly to inject before every single response.

    Also stamps _LAST_ACTIVITY_FILE with the current time on every call -- since this fires
    on every UserPromptSubmit across every session (not just one), it's the natural shared
    heartbeat for cmd_daily_check's sleep-detection, without needing a dedicated hook of its
    own."""
    _LAST_ACTIVITY_FILE.write_text(str(time.time()))
    print(_TREE_REMINDER)


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
    print(_DAILY_CHECK_PRIME)


def cmd_session_register(args: argparse.Namespace) -> None:
    """Read a session ID on stdin (SessionStart's own JSON envelope's .session_id, matching
    daily-check's convention), falling back to current_session_id() for manual testing.
    Registers/refreshes this session as live -- see HarnessSession.register (models.py) and
    kb Goal #46 for the full cross-session-messaging design this feeds. Title is left unset
    here (SessionStart's envelope doesn't carry a resolved title yet); `kb sessions list`
    reads whatever HarnessSession.title holds, empty until something else backfills it."""
    from harness import current_session_id
    from models import HarnessSession

    from kb_cli.sessions import _find_claude_ancestor_pid

    session_id = sys.stdin.read().strip()
    if not session_id:
        session_id = current_session_id() or ""
    if not session_id:
        return
    HarnessSession.register(args.session, session_id, cwd=os.getcwd(), pid=_find_claude_ancestor_pid())
    args.session.commit()


def cmd_session_inbox_check(args: argparse.Namespace) -> None:
    """Layer 1 of kb Goal #46's cross-session messaging delivery: called from
    UserPromptSubmit on every prompt, prints any of this session's unread SessionMessages
    (marking them read). `kb sessions listen` (Layer 2, proactive delivery) is opt-in, not
    started or nagged-for by default -- forcing it onto every session proved too heavyweight
    once kb had more than one user (see CLAUDE_GLOBAL.md's own history and kb Goal #23/#46).
    A session that never runs Layer 2 simply only sees messages via this per-prompt check,
    which is an acceptable degraded mode, not an error state to nag about."""
    from base import _now
    from harness import current_session_id
    from models import ChannelMessage, ChannelRead, HarnessSession, HarnessSessionStatus

    session_id = current_session_id()
    if not session_id:
        return
    row = args.session.get(HarnessSession, session_id)
    if row is not None:
        row.status = HarnessSessionStatus.INFERRING
        row.last_active_at = _now()
        args.session.commit()
    messages = ChannelMessage.unread(args.session, session_id)
    lines = [f"New message from session {msg.from_session}:\n  {msg.body}" for msg in messages]
    channel_ids = {msg.channel_id for msg in messages}
    for channel_id in channel_ids:
        ChannelRead.record(args.session, channel_id=channel_id, session_id=session_id)
    if messages:
        args.session.commit()

    if lines:
        print("\n\n".join(lines))


def cmd_session_stop(args: argparse.Namespace) -> None:
    """Called from the Stop hook -- marks this session IDLE and bumps last_response_at.
    Silent always (no stdout), this only updates HarnessSession bookkeeping for kb sessions
    list to show honest live-status info, per kb Goal #46's design discussion."""
    from base import _now
    from harness import current_session_id
    from models import HarnessSession, HarnessSessionStatus

    session_id = current_session_id()
    if not session_id:
        return
    row = args.session.get(HarnessSession, session_id)
    if row is None:
        return
    row.status = HarnessSessionStatus.IDLE
    row.last_response_at = _now()
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
        "print a session-persistence-review reminder if it matches",
    )
    p_post_commit.set_defaults(func=cmd_post_commit_check)

    p_find_root = sub.add_parser(
        "find-root-check",
        help="Detect a `find /` (root-scoped) command on stdin; print a block reason if it matches",
    )
    p_find_root.set_defaults(func=cmd_find_root_check)

    p_dep_install = sub.add_parser(
        "dependency-install-check",
        help="Detect a new-dependency install command on stdin; require AUDITED=noteN or print a block reason",
    )
    p_dep_install.set_defaults(func=cmd_dependency_install_check)

    p_sessions_listen = sub.add_parser(
        "sessions-listen-check",
        help="Detect `kb sessions listen` shell-backgrounded (nohup/setsid/disown/&) on stdin; print a block reason if it matches",
    )
    p_sessions_listen.set_defaults(func=cmd_sessions_listen_check)

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
        help="Unconditional one-line reminder to re-check the Instruction tree for mid-task relevance",
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
