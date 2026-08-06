"""System instructions -- shipped with kb itself via git, not stored in the DB. Distinct
from `kb instructions` (`kb i`), which is one user's own Instruction tree in the DB: personal
context, overrides, anything a user has added. `kb si root`'s content is identical for
anyone running this project and is versioned with the code, same as any other file in this
repo -- forking it is an ordinary git fork, not a kb mechanism.

See docs/si_root.md for the actual content and kb Goal #23 for the split's design rationale.
"""

import argparse
from pathlib import Path

_SI_ROOT_PATH = Path(__file__).resolve().parent.parent / "docs" / "si_root.md"


def cmd_root(args: argparse.Namespace) -> None:
    print(_SI_ROOT_PATH.read_text(), end="")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("si", help="System instructions (shipped with kb, same for every user)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_root = sub.add_parser("root", help="Print kb's system instructions (docs/si_root.md)")
    p_root.set_defaults(func=cmd_root)
