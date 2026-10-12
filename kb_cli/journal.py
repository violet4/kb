"""Journal operations."""

import argparse
import sys

from harness import current_session_id
from kb_cli._util import journal_lines, resolve_text_arg
from models import HarnessSession, Journal


def cmd_add(args: argparse.Namespace) -> None:
    entry = Journal.record(args.session, args.entity_type, args.entity_id, note=resolve_text_arg(args.note))
    args.session.commit()
    print(entry)


def cmd_show(args: argparse.Namespace) -> None:
    entries = Journal.for_entity(args.session, args.entity_type, args.entity_id, include_reads=args.reads)
    if not entries:
        print("No journal entries.")
        return
    for line in journal_lines(entries):
        print(line)


def cmd_session(args: argparse.Namespace) -> None:
    harness_id = args.harness_id or current_session_id()
    if harness_id is None:
        print("kb journal session: pass a session id (none detected for this process)", file=sys.stderr)
        sys.exit(1)
    row = HarnessSession.by_harness_id(args.session, harness_id)
    if row is None:
        print(f"kb journal session: no registered session {harness_id}", file=sys.stderr)
        sys.exit(1)
    entries = Journal.for_session(args.session, row.id)
    if not entries:
        print("No journal entries.")
        return
    for line in journal_lines(entries, with_entity=True):
        print(line)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("journal", help="Journal operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Record a free-text journal note for an entity")
    p_add.add_argument("entity_type")
    p_add.add_argument("entity_id", type=int)
    p_add.add_argument("note")
    p_add.set_defaults(func=cmd_add)

    p_show = sub.add_parser("show", help="Show journal history for an entity")
    p_show.add_argument("entity_type")
    p_show.add_argument("entity_id", type=int)
    p_show.add_argument("--reads", action="store_true", help="Include reads, not only changes and notes")
    p_show.set_defaults(func=cmd_show)

    p_session = sub.add_parser(
        "session", help="Show everything one agent session did to kb records (creates, changes, reads)"
    )
    p_session.add_argument("harness_id", nargs="?", help="Session id (default: this session)")
    p_session.set_defaults(func=cmd_session)
