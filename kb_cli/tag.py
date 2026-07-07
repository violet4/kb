"""TodoTag hierarchy management -- creating tags, wiring parent/child relationships."""
import argparse
import sys

from sqlalchemy import select

from models import TodoTag

from kb_cli._util import get_by_name


def cmd_add(args: argparse.Namespace) -> None:
    existing = args.session.scalars(select(TodoTag).where(TodoTag.name == args.name)).one_or_none()
    if existing is not None:
        print(f"TodoTag {args.name!r} already exists (#{existing.id})", file=sys.stderr)
        sys.exit(1)
    parent = get_by_name(args.session, TodoTag, args.parent) if args.parent else None
    tag = TodoTag(name=args.name, parent=parent)
    args.session.add(tag)
    args.session.commit()
    print(tag)


def cmd_show(args: argparse.Namespace) -> None:
    tag = get_by_name(args.session, TodoTag, args.name)
    chain = " -> ".join(t.name for t in tag.ancestors())
    print(f"id: {tag.id}")
    print(f"name: {tag.name}")
    print(f"hierarchy: {chain}")


def cmd_set_parent(args: argparse.Namespace) -> None:
    tag = get_by_name(args.session, TodoTag, args.name)
    parent = get_by_name(args.session, TodoTag, args.parent) if args.parent else None
    tag.parent = parent
    args.session.commit()
    print(tag)


def cmd_list(args: argparse.Namespace) -> None:
    tags = args.session.scalars(select(TodoTag).order_by(TodoTag.name)).all()
    if not tags:
        print("No tags.")
        return
    for t in tags:
        print(t)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("tag", help="TodoTag hierarchy operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Create a tag, optionally under a parent tag")
    p_add.add_argument("name")
    p_add.add_argument("--parent", help="Parent tag name (must already exist)")
    p_add.set_defaults(func=cmd_add)

    p_show = sub.add_parser("show", help="Show a tag and its ancestor chain")
    p_show.add_argument("name")
    p_show.set_defaults(func=cmd_show)

    p_set_parent = sub.add_parser("set-parent", help="Change (or clear) a tag's parent")
    p_set_parent.add_argument("name")
    p_set_parent.add_argument("parent", nargs="?", help="Omit to clear the parent")
    p_set_parent.set_defaults(func=cmd_set_parent)

    p_list = sub.add_parser("list", help="List all tags")
    p_list.set_defaults(func=cmd_list)
