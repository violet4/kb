"""`kb claude [ARGS...]` -- run `claude ARGS...` so the session accepts prompts from other
processes (the web UI's agent page), on top of the user's own terminal. See harness_input.py
for the mechanism."""

import argparse
import sys

import harness_input


def cmd_claude(args: argparse.Namespace) -> None:
    # The session can run for hours; holding kb.db open that long would block migrations.
    args.session.close()
    args.session.get_bind().dispose()
    sys.exit(harness_input.run(args.claude_args))


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    # A prefix character no real argument starts with makes every argument positional, so
    # `kb claude --resume ID` and `kb claude --help` reach `claude` untouched.
    p = subparsers.add_parser(
        "claude",
        help="Run `claude ARGS...` so the web UI's agent page can send prompts to the session",
        prefix_chars="\0",
        add_help=False,
    )
    p.add_argument("claude_args", nargs="*")
    p.set_defaults(func=cmd_claude)
