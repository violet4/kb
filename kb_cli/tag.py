"""Tag operations -- flat labels attached to Context (many-to-many) or addressed
directly by Goal/Todo/Daily/Idea (tag_id, mutually exclusive with context_id).
See models.Context/Tag for the design."""

import argparse
import sys

from sqlalchemy import select

from models import Tag


def cmd_add(args: argparse.Namespace) -> None:
    existing = args.session.scalars(select(Tag).where(Tag.name == args.name)).one_or_none()
    if existing is not None:
        print(f"Tag {args.name!r} already exists (#{existing.id})", file=sys.stderr)
        sys.exit(1)
    tag = Tag(name=args.name)
    args.session.add(tag)
    args.session.commit()
    print(tag)


def cmd_list(args: argparse.Namespace) -> None:
    tags = args.session.scalars(select(Tag).order_by(Tag.name)).all()
    if not tags:
        print("No tags.")
        return
    for t in tags:
        print(t)


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("tag", help="Tag operations (flat labels)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Create a tag")
    p_add.add_argument("name")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List all tags")
    p_list.set_defaults(func=cmd_list)
