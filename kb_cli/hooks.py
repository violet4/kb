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


_TREE_REMINDER = (
    "Re-check the Instruction tree for a child relevant to what you're about to do now, not just at session start."
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

    p_find_root = sub.add_parser(
        "find-root-check",
        help="Detect a `find /` (root-scoped) command on stdin; print a block reason if it matches",
    )
    p_find_root.set_defaults(func=cmd_find_root_check)

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
