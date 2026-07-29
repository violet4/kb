"""Interim URL capture ahead of a live ArchiveBox instance -- see ArchivedLink's docstring
in models.py and kb Todo #70 for the eventual real-ArchiveBox integration."""

import argparse
import sys

from models import ArchivedLink


def cmd_add(args: argparse.Namespace) -> None:
    link = ArchivedLink.create(args.session, args.url, note=args.note)
    args.session.commit()
    print(link)
    print(f"AB{link.id} -- embed this ID in whatever note/todo/journal entry cites {link.url}")


def cmd_list(args: argparse.Namespace) -> None:
    links = ArchivedLink.pending(args.session)
    if not links:
        print("No pending links.")
        return
    for link in links:
        note = f" -- {link.note}" if link.note else ""
        print(f"AB{link.id} {link.created_at:%Y-%m-%d %H:%M} {link.url}{note}")


def cmd_show(args: argparse.Namespace) -> None:
    link = args.session.get(ArchivedLink, args.id)
    if link is None:
        print(f"AB{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    print(link)
    if link.note:
        print(f"note: {link.note}")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("ab", help="ArchiveBox URL capture (interim -- not wired to a live instance yet)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Save a URL with a timestamp for later archival")
    p_add.add_argument("url")
    p_add.add_argument("--note")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List URLs not yet migrated to a live ArchiveBox instance")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Resolve an ABn id back to its URL/note")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_show)
