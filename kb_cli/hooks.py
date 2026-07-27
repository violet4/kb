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
import re
import sys

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


_TREE_REMINDER = (
    "Re-check the Instruction tree for a child relevant to what you're about to do now, not just at session start."
)


def cmd_tree_reminder(args: argparse.Namespace) -> None:
    """Unconditional -- always prints the same short reminder, no stdin/detection needed.
    Deterministic backstop for kb Goal #23's finding that per-node triggers don't reliably
    fire mid-task from root's own wording alone (root is read once, at the first tool call
    of a session, with no built-in re-entry point when a new sub-situation arises later).
    Kept to one line by design: Goal #23's Journal explicitly rejected a longer per-topic
    checklist as too costly to inject before every single response."""
    print(_TREE_REMINDER)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "hooks", help="Harness-agnostic hook detectors -- read command output on stdin, print a reminder on a match"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mypy = sub.add_parser(
        "mypy-check", help="Detect a failed mypy run on stdin; print a type-safety reminder if it matches"
    )
    p_mypy.set_defaults(func=cmd_mypy_check)

    p_tree = sub.add_parser(
        "tree-reminder",
        help="Unconditional one-line reminder to re-check the Instruction tree for mid-task relevance",
    )
    p_tree.set_defaults(func=cmd_tree_reminder)
