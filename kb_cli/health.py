"""Structural health checks over kb's own data -- distinct from `kb stats` (volume/activity
counts) in that these are invariant checks: a condition that should always hold and, if it
doesn't, indicates silent data corruption rather than just "here's how much stuff there is."

Currently covers exactly one invariant: the Instruction tree must have exactly one root
(Instruction.roots() returning more than one row means some node lost its "parent-of"
EntityLink and is now floating disconnected from the tree, invisible to normal `kb i show`
navigation from root -- see kb Instruction #83's incident for the motivating case, found
2026-09-01, orphaned since 2026-08-23 with nobody noticing). `roots()` itself already defines
what "no incoming parent-of edge" means (models.py); this module doesn't redefine that, it
just asks whether more than one such node exists and, if so, which ones beyond the one
actually titled "root".

Other structural invariants (broken/dangling EntityLinks, stale nodes, etc.) are plausible
future additions here but out of scope for now -- this module intentionally checks only the
Instruction-root invariant until a second one is actually needed."""

import argparse
import sys

from sqlalchemy.orm import Session

from models import Instruction


def _orphans(session: Session) -> list[Instruction]:
    """Every Instruction.roots() row except the one actually titled "root" -- the tree's one
    true entry point. A healthy tree has roots() == [that one node]; anything else in the
    list is a node that lost its "parent-of" EntityLink and is now an orphaned second root."""
    return [node for node in Instruction.roots(session) if node.title != "root"]


def cmd_check(args: argparse.Namespace) -> None:
    orphans = _orphans(args.session)
    if not orphans:
        print("Instruction tree: OK (1 root)")
        return
    print(f"Instruction tree: {len(orphans)} orphaned node(s) -- run `kb health orphans` for detail")
    sys.exit(1)


def cmd_orphans(args: argparse.Namespace) -> None:
    orphans = _orphans(args.session)
    if not orphans:
        print("No orphaned Instruction nodes")
        return
    for node in orphans:
        print(f"#{node.id} {node.title}")
    sys.exit(1)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("health", help="Structural health checks over kb's own data")
    sub = parser.add_subparsers(dest="cmd", required=False)

    p_check = sub.add_parser("check", help="Summary count of orphaned Instruction nodes (default)")
    p_check.set_defaults(func=cmd_check)

    p_orphans = sub.add_parser("orphans", help="List orphaned Instruction nodes' ids and titles")
    p_orphans.set_defaults(func=cmd_orphans)

    parser.set_defaults(func=cmd_check)
