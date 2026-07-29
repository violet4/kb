"""Interim URL capture ahead of a live ArchiveBox instance -- see ArchivedLink's docstring
in models.py and kb Todo #70 for the eventual real-ArchiveBox integration."""

import argparse
import sys

from models import ArchivedLink


def cmd_add(args: argparse.Namespace) -> None:
    link = ArchivedLink.create(args.session, args.url, args.title, args.reason)
    args.session.commit()
    print(link)
    print(f"AB{link.id} -- embed this ID in whatever note/todo/journal entry cites {link.url}")
    title_bytes = len(link.title.encode())
    reason_bytes = len(link.reason.encode())
    print(f"title: {link.title!r}")
    print(f"reason ({reason_bytes} bytes): {link.reason!r}")
    if title_bytes > reason_bytes:
        print(
            f"warning: title ({title_bytes} bytes) is longer than reason ({reason_bytes} bytes) "
            "-- reason is meant to carry the why, double check it isn't just a restated title"
        )


def cmd_list(args: argparse.Namespace) -> None:
    links = ArchivedLink.pending(args.session)
    if not links:
        print("No pending links.")
        return
    for link in links:
        print(f"AB{link.id} {link.created_at:%Y-%m-%d %H:%M} {link.title!r} {link.url} -- {link.reason}")


def cmd_show(args: argparse.Namespace) -> None:
    link = args.session.get(ArchivedLink, args.id)
    if link is None:
        print(f"AB{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    print(link)
    print(f"url: {link.url}")
    print(f"reason: {link.reason}")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("ab", help="ArchiveBox URL capture (interim -- not wired to a live instance yet)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser(
        "add",
        help="Save a URL with a title and required reason -- never save a bare link with no record of why it matters",
    )
    p_add.add_argument("url")
    p_add.add_argument("title", help="Neutral description of what the page/content is, not why it was saved")
    p_add.add_argument("reason", help="Why this was worth keeping -- what made it pass the filter")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List URLs not yet migrated to a live ArchiveBox instance")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Resolve an ABn id back to its URL/title/reason")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_show)
