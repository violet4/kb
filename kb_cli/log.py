"""Log operations."""

import argparse
from datetime import datetime, timezone

from context import resolve_context
from models import LogEntry


def cmd_add(args: argparse.Namespace) -> None:
    context = resolve_context(args.session, args.context)
    occurred_at = None
    if args.date:
        occurred_at = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    entry = LogEntry.create(args.session, body=args.body, domain=args.domain, context=context, occurred_at=occurred_at)
    args.session.commit()
    print(entry)


def cmd_recent(args: argparse.Namespace) -> None:
    context = resolve_context(args.session, args.context) if args.context else None
    entries = LogEntry.recent(args.session, domain=args.domain, context=context, limit=args.limit)
    if not entries:
        print("No entries.")
        return
    for e in entries:
        when = e.occurred_at.strftime("%Y-%m-%d %H:%M")
        domain = f" [{e.domain}]" if e.domain else ""
        print(f"#{e.id} {when}{domain}: {e.body}")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("log", help="Log operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a log entry")
    p_add.add_argument("body")
    p_add.add_argument("--domain", help="Loose category label, e.g. 'health', 'cat', 'work'")
    p_add.add_argument("--context", metavar="NAME", help="Attach to a specific context instead of the current one")
    p_add.add_argument("--date", metavar="YYYY-MM-DD", help="Backdate the entry (default: now)")
    p_add.set_defaults(func=cmd_add)

    p_recent = sub.add_parser("recent", help="Show recent log entries")
    p_recent.add_argument("--domain", help="Only show this domain")
    p_recent.add_argument("--context", metavar="NAME", help="Only show entries in this context")
    p_recent.add_argument("--limit", type=int, default=20)
    p_recent.set_defaults(func=cmd_recent)
