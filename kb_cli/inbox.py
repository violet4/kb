"""Inbox operations."""
import argparse
import sys

from models import InboxItem


def cmd_add(args: argparse.Namespace) -> None:
    item = InboxItem.create(args.session, args.body, source=args.source, category=args.category)
    args.session.commit()
    print(item)


def cmd_pending(args: argparse.Namespace) -> None:
    items = InboxItem.pending(args.session, category=args.category)
    if not items:
        print("Inbox empty.")
        return
    for i in items:
        print(i)


def cmd_triage(args: argparse.Namespace) -> None:
    for item_id in args.ids:
        item = args.session.get(InboxItem, item_id)
        if item is None:
            print(f"InboxItem #{item_id}: not found", file=sys.stderr)
            continue
        item.triage()
        body = item.body if len(item.body) <= 60 else item.body[:60] + "…"
        print(f"InboxItem #{item_id}: {body!r} -> triaged")
    args.session.commit()


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("inbox", help="Inbox operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a raw, untriaged item")
    p_add.add_argument("body")
    p_add.add_argument("--source", help="capture channel, e.g. 'email', 'mobile', 'quick-note'")
    p_add.add_argument("--category", help="kind of content, e.g. 'project-idea', 'purchase'")
    p_add.set_defaults(func=cmd_add)

    p_pending = sub.add_parser("pending", help="List untriaged items")
    p_pending.add_argument("--category", help="filter to items of this category")
    p_pending.set_defaults(func=cmd_pending)

    p_triage = sub.add_parser("triage", help="Mark item(s) triaged (after creating whatever real record they became)")
    p_triage.add_argument("ids", nargs="+", type=int)
    p_triage.set_defaults(func=cmd_triage)
