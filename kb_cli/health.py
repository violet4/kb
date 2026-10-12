"""Structural health checks over kb's own data and its harness wiring -- distinct from `kb
stats` (volume/activity counts) in that these are invariant checks: a condition that should
always hold and, if it doesn't, means data or attribution is silently going wrong rather than
just "here's how much stuff there is."

Two invariants:

- The Instruction tree has exactly one root. Instruction.roots() returning more than one row
  means some node lost its "parent-of" EntityLink and is floating disconnected from the tree,
  invisible to normal `kb i show` navigation from root (kb Instruction #83's incident).
- An agent session is registered. When the harness exposes a session id
  (harness.current_session_id()) but no HarnessSession row exists for it, every Journal row
  this session writes carries no session, so its work is missing from `kb journal session`
  and everything built on it. The usual cause is a harness whose session-start hook does not
  call `kb hooks session-register`; docs/harnesses/ has the wiring per harness."""

import argparse
import sys

from sqlalchemy.orm import Session

from harness import current_session_id
from models import HarnessSession, Instruction


def _orphans(session: Session) -> list[Instruction]:
    """Every Instruction.roots() row except the one actually titled "root" -- the tree's one
    true entry point. A healthy tree has roots() == [that one node]; anything else in the
    list is a node that lost its "parent-of" EntityLink and is now an orphaned second root."""
    return [node for node in Instruction.roots(session) if node.title != "root"]


def _check_instruction_tree(session: Session) -> bool:
    orphans = _orphans(session)
    if not orphans:
        print("Instruction tree: OK (1 root)")
        return True
    print(f"Instruction tree: {len(orphans)} orphaned node(s) -- run `kb health orphans` for detail")
    return False


def _check_session_registered(session: Session) -> bool:
    harness_id = current_session_id()
    if harness_id is None:
        print("Agent session: none detected (not running inside a known harness)")
        return True
    if HarnessSession.by_harness_id(session, harness_id) is not None:
        print(f"Agent session: OK ({harness_id} registered)")
        return True
    print(
        f"Agent session: {harness_id} is NOT registered -- its kb activity is journaled without a session. "
        "Wire your harness's session-start hook to `kb hooks session-register` (see docs/harnesses/), "
        "or run `kb hooks session-register` once for this session."
    )
    return False


def cmd_check(args: argparse.Namespace) -> None:
    results = [_check_instruction_tree(args.session), _check_session_registered(args.session)]
    if not all(results):
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
    parser = subparsers.add_parser("health", help="Health checks over kb's own data and its harness wiring")
    sub = parser.add_subparsers(dest="cmd", required=False)

    p_check = sub.add_parser(
        "check", help="Run every check: Instruction tree root, agent session registration (default)"
    )
    p_check.set_defaults(func=cmd_check)

    p_orphans = sub.add_parser("orphans", help="List orphaned Instruction nodes' ids and titles")
    p_orphans.set_defaults(func=cmd_orphans)

    parser.set_defaults(func=cmd_check)
