"""Goal operations."""

import argparse
import sys
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from context import creation_context
from models import Goal, GoalStatus, Journal

from kb_cli._util import (
    add_history_arg,
    apply_context_or_tag_update,
    apply_updates,
    print_journal_history,
    scope_to_context,
)
from kb_cli.search import cmd_search


def cmd_add(args: argparse.Namespace) -> None:
    goal = Goal.create(
        args.session, args.title, description=args.description, context=creation_context(args), notes=args.notes
    )
    args.session.commit()
    print(goal)


def cmd_update(args: argparse.Namespace) -> None:
    goal = apply_updates(
        args.session,
        Goal,
        args.id,
        "Goal",
        {
            "title": args.title,
            "description": args.description,
            "notes": args.notes,
        },
    )
    apply_context_or_tag_update(args.session, goal, args.new_context, args.new_tag)
    args.session.commit()
    print(goal)


def cmd_show(args: argparse.Namespace) -> None:
    for i, goal_id in enumerate(args.ids):
        if i > 0:
            print()
        goal = args.session.get(Goal, goal_id)
        if goal is None:
            print(f"id: {goal_id}\nerror: not found", file=sys.stderr)
            continue
        print(f"id: {goal.id}")
        print(f"title: {goal.title}")
        print(f"status: {goal.status.value}")
        if goal.description:
            print(f"description: {goal.description}")
        if goal.context:
            print(f"context: {goal.context.name}")
        if goal.notes:
            print(f"notes: {goal.notes}")

        print_journal_history(
            args.session,
            Journal,
            "Goal",
            goal.id,
            args.history,
            f"journal show Goal {goal.id} or kb goal show {goal.id} --history [N]",
        )


def cmd_list(args: argparse.Namespace) -> None:
    status = GoalStatus(args.status) if args.status else None
    if status is not None and status != GoalStatus.ACTIVE:
        # Goal.active() only returns ACTIVE Goals -- an explicit non-ACTIVE status needs a
        # plain query instead. --all still applies to this query as scoping-only, same as
        # the ACTIVE-status branch below.
        q = select(Goal).where(Goal.status == status)
        if not args.all:
            in_scope = scope_to_context(args.session, args.context)
            if in_scope is not None:
                match = Goal.matches_contexts(in_scope)
                q = q.where(match | (Goal.context_id.is_(None) & Goal.tag_id.is_(None)))
        goals = args.session.scalars(q).all()
    elif args.all:
        goals = Goal.active(args.session)
    else:
        in_scope = scope_to_context(args.session, args.context)
        goals = Goal.active(args.session, contexts=in_scope, include_no_context=True)
    if not goals:
        print("No goals.")
        return
    for g in goals:
        print(f"#{g.id} [{g.status.value}] {g.title}")


def _set_status(session: Session, ids: Iterable[int], status: GoalStatus, verb: str) -> None:
    for goal_id in ids:
        goal = session.get(Goal, goal_id)
        if goal is None:
            print(f"Goal #{goal_id}: not found", file=sys.stderr)
            continue
        goal.status = status
        print(f"Goal #{goal_id}: {goal.title!r} -> {verb}")
    session.commit()


def cmd_complete(args: argparse.Namespace) -> None:
    _set_status(args.session, args.ids, GoalStatus.COMPLETED, "completed")


def cmd_abandon(args: argparse.Namespace) -> None:
    _set_status(args.session, args.ids, GoalStatus.ABANDONED, "abandoned")


def cmd_hold(args: argparse.Namespace) -> None:
    _set_status(args.session, args.ids, GoalStatus.ON_HOLD, "on hold")


def cmd_reactivate(args: argparse.Namespace) -> None:
    _set_status(args.session, args.ids, GoalStatus.ACTIVE, "active")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("goal", aliases=["g"], help="Goal operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a Goal")
    p_add.add_argument("title")
    p_add.add_argument("--description")
    p_add.add_argument("--notes")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update fields on an existing Goal")
    p_update.add_argument("id", type=int)
    p_update.add_argument("--title")
    p_update.add_argument("--description")
    p_update.add_argument("--notes")
    p_update_ctx = p_update.add_mutually_exclusive_group()
    p_update_ctx.add_argument("--context", dest="new_context", metavar="NAME")
    p_update_ctx.add_argument("--tag", dest="new_tag", metavar="NAME")
    p_update.set_defaults(func=cmd_update)

    p_show = sub.add_parser("show", help="Show Goal details")
    p_show.add_argument("ids", nargs="+", type=int)
    add_history_arg(p_show)
    p_show.set_defaults(func=cmd_show)

    p_complete = sub.add_parser("complete", help="Mark Goal(s) completed")
    p_complete.add_argument("ids", nargs="+", type=int)
    p_complete.set_defaults(func=cmd_complete)

    p_abandon = sub.add_parser("abandon", help="Mark Goal(s) abandoned")
    p_abandon.add_argument("ids", nargs="+", type=int)
    p_abandon.set_defaults(func=cmd_abandon)

    p_hold = sub.add_parser("hold", help="Mark Goal(s) on hold")
    p_hold.add_argument("ids", nargs="+", type=int)
    p_hold.set_defaults(func=cmd_hold)

    p_reactivate = sub.add_parser("reactivate", help="Mark Goal(s) active again")
    p_reactivate.add_argument("ids", nargs="+", type=int)
    p_reactivate.set_defaults(func=cmd_reactivate)

    p_list = sub.add_parser("list", help="List Goals, everywhere by default (or scoped to --context)")
    p_list.add_argument("--status", choices=[s.value for s in GoalStatus])
    p_list.add_argument(
        "--all", action="store_true", help="Ignore an active --context and show Goals from every context"
    )
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser(
        "search",
        help="Search Goals by text (unscoped by default; pass the global "
        "`kb --context NAME goal search ...` to restrict to that context's subtree)",
    )
    p_search.add_argument("query")
    p_search.add_argument(
        "--all", action="store_true", help="Also include completed/abandoned Goals (excluded by default)"
    )
    p_search.set_defaults(func=cmd_search, model=Goal)
