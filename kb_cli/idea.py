"""Idea operations (GTD Someday/Maybe) -- see Idea's docstring in models.py."""

import argparse
import sys

from sqlalchemy import select

from context import resolve_context
from models import Context, Idea, IdeaStatus, Journal

from kb_cli._util import add_history_arg, print_journal_history


def cmd_add(args: argparse.Namespace) -> None:
    idea = Idea.create(args.session, args.title, description=args.description, context=args.context, notes=args.notes)
    args.session.commit()
    print(idea)


def cmd_show(args: argparse.Namespace) -> None:
    for i, idea_id in enumerate(args.ids):
        if i > 0:
            print()
        idea = args.session.get(Idea, idea_id)
        if idea is None:
            print(f"id: {idea_id}\nerror: not found", file=sys.stderr)
            continue
        print(f"id: {idea.id}")
        print(f"title: {idea.title}")
        print(f"status: {idea.status.value}")
        if idea.description:
            print(f"description: {idea.description}")
        if idea.context:
            print(f"context: {idea.context.name}")
        if idea.notes:
            print(f"notes: {idea.notes}")

        print_journal_history(
            args.session,
            Journal,
            "Idea",
            idea.id,
            args.history,
            f"journal show Idea {idea.id} or kb idea show {idea.id} --history [N]",
        )


def cmd_list(args: argparse.Namespace) -> None:
    if args.all:
        ideas = args.session.scalars(select(Idea).where(Idea.status == IdeaStatus.ACTIVE)).all()
    else:
        current = resolve_context(args.session)
        in_scope = Context.self_and_descendants(args.session, current.name) if current else None
        ideas = Idea.active(args.session, contexts=in_scope, include_no_context=True)
    if not ideas:
        print("No ideas.")
        return
    for i in ideas:
        ctx = f" [{i.context.name}]" if i.context else ""
        print(f"#{i.id} {i.title}{ctx}")


def cmd_promote(args: argparse.Namespace) -> None:
    idea = args.session.get(Idea, args.id)
    if idea is None:
        print(f"Idea #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    idea.status = IdeaStatus.PROMOTED
    Journal.record(args.session, "Idea", idea.id, note=f"promoted: {args.to}")
    args.session.commit()
    print(f"Idea #{idea.id}: {idea.title!r} -> promoted ({args.to})")


def cmd_drop(args: argparse.Namespace) -> None:
    idea = args.session.get(Idea, args.id)
    if idea is None:
        print(f"Idea #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    idea.status = IdeaStatus.DROPPED
    args.session.commit()
    print(f"Idea #{idea.id}: {idea.title!r} -> dropped")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "idea", help="Someday/maybe ideas -- reviewed deliberately, never surfaced on their own"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add an idea")
    p_add.add_argument("title")
    p_add.add_argument("--description")
    p_add.add_argument("--notes")
    p_add.set_defaults(func=cmd_add)

    p_show = sub.add_parser("show", help="Show idea details")
    p_show.add_argument("ids", nargs="+", type=int)
    add_history_arg(p_show)
    p_show.set_defaults(func=cmd_show)

    p_list = sub.add_parser("list", help="List active ideas, scoped to the current context by default")
    p_list.add_argument("--all", action="store_true", help="Ignore context scoping and show ideas from every context")
    p_list.set_defaults(func=cmd_list)

    p_promote = sub.add_parser("promote", help="Mark an idea promoted -- record what it became in its Journal")
    p_promote.add_argument("id", type=int)
    p_promote.add_argument("--to", required=True, help="Description of what it became, e.g. 'Goal #14'")
    p_promote.set_defaults(func=cmd_promote)

    p_drop = sub.add_parser("drop", help="Mark an idea dropped")
    p_drop.add_argument("id", type=int)
    p_drop.set_defaults(func=cmd_drop)
