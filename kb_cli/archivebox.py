"""Interim URL capture ahead of a live ArchiveBox instance -- see ArchivedLink's docstring
in models.py and kb Todo #70 for the eventual real-ArchiveBox integration."""

import argparse

from models import ArchivedLink


def cmd_add(args: argparse.Namespace) -> None:
    link = ArchivedLink.create(args.session, args.url, note=args.note)
    args.session.commit()
    print(link)


def cmd_list(args: argparse.Namespace) -> None:
    links = ArchivedLink.pending(args.session)
    if not links:
        print("No pending links.")
        return
    for link in links:
        note = f" -- {link.note}" if link.note else ""
        print(f"#{link.id} {link.created_at:%Y-%m-%d %H:%M} {link.url}{note}")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("ab", help="ArchiveBox URL capture (interim -- not wired to a live instance yet)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Save a URL with a timestamp for later archival")
    p_add.add_argument("url")
    p_add.add_argument("--note")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List URLs not yet migrated to a live ArchiveBox instance")
    p_list.set_defaults(func=cmd_list)
