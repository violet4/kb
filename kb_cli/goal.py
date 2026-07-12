"""Goal operations."""

import argparse
import sys
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from context import resolve_context
from models import Context, Goal, GoalStatus, Journal

from kb_cli._util import add_history_arg, print_journal_history


def cmd_add(args: argparse.Namespace) -> None:
    goal = Goal.create(args.session, args.title, description=args.description, context=args.context, notes=args.notes)
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
    if args.all:
        # Goal.active() only returns ACTIVE Goals -- an explicit non-ACTIVE status or no
        # status filter at all both need a plain query instead.
        q = select(Goal)
        if status is not None:
            q = q.where(Goal.status == status)
        goals = args.session.scalars(q).all()
    elif status is not None and status != GoalStatus.ACTIVE:
        goals = args.session.scalars(select(Goal).where(Goal.status == status)).all()
    else:
        current = resolve_context(args.session)
        in_scope = Context.self_and_descendants(args.session, current.name) if current else None
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
    parser = subparsers.add_parser("goal", help="Goal operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a Goal")
    p_add.add_argument("title")
    p_add.add_argument("--description")
    p_add.add_argument("--notes")
    p_add.set_defaults(func=cmd_add)

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

    p_list = sub.add_parser("list", help="List Goals, scoped to the current context by default")
    p_list.add_argument("--status", choices=[s.value for s in GoalStatus])
    p_list.add_argument("--all", action="store_true", help="Ignore context scoping and show Goals from every context")
    p_list.set_defaults(func=cmd_list)
