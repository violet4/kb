"""Goal operations."""

import argparse
import sys
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from context import resolve_placement
from models import Goal, GoalStatus, Journal

from kb_cli._util import (
    journal_read,
    add_context_filter_argument,
    add_history_arg,
    add_placement_argument,
    apply_context_or_tag_update,
    apply_purge,
    apply_restore,
    apply_soft_delete,
    apply_updates,
    print_journal_history,
    print_links,
    print_timestamps,
    resolve_text_arg,
    scope_to_context,
)
from kb_cli.search import cmd_search_deprecated


def cmd_add(args: argparse.Namespace) -> None:
    place = resolve_placement(args.session, args.place)
    goal = Goal.create(
        args.session,
        args.title,
        description=resolve_text_arg(args.description) if args.description else args.description,
        context=place.context,
        tag=place.tag,
        notes=resolve_text_arg(args.notes) if args.notes else args.notes,
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
            "description": resolve_text_arg(args.description) if args.description else args.description,
            "notes": resolve_text_arg(args.notes) if args.notes else args.notes,
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
        journal_read(args.session, "Goal", goal.id)
        print(f"id: {goal.id}")
        print(f"title: {goal.title}")
        print(f"status: {goal.status.value}")
        if goal.description:
            print(f"description: {goal.description}")
        if goal.context:
            print(f"context: {goal.context.name}")
        if goal.notes:
            print(f"notes: {goal.notes}")
        print_timestamps(goal)

        print_journal_history(
            args.session,
            Journal,
            "Goal",
            goal.id,
            args.history,
            f"journal show Goal {goal.id} or kb goal show {goal.id} --history [N]",
        )
        print_links(args.session, "Goal", goal.id)


def cmd_list(args: argparse.Namespace) -> None:
    status = GoalStatus(args.status) if args.status else None
    in_scope = scope_to_context(args.session, args.context_name)
    if status is not None and status != GoalStatus.ACTIVE:
        # Goal.active() only returns ACTIVE Goals -- an explicit non-ACTIVE status needs a
        # plain query instead, scoped the same way.
        q = select(Goal).where(Goal.status == status, Goal.deleted_at.is_(None))
        if in_scope is not None:
            q = q.where(Goal.matches_contexts(in_scope))
        goals = args.session.scalars(q).all()
    else:
        goals = Goal.active(args.session, contexts=in_scope)
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


def cmd_delete(args: argparse.Namespace) -> None:
    goal = apply_soft_delete(args.session, Goal, args.id, "Goal")
    args.session.commit()
    print(f"Goal #{goal.id} {goal.title!r}: soft-deleted (restore with `kb goal restore {goal.id}`)")


def cmd_restore(args: argparse.Namespace) -> None:
    goal = apply_restore(args.session, Goal, args.id, "Goal")
    args.session.commit()
    print(f"Goal #{goal.id} {goal.title!r}: restored")


def cmd_purge(args: argparse.Namespace) -> None:
    goal = apply_purge(args.session, Goal, args.id, "Goal", args.force_delete_links)
    args.session.commit()
    print(f"Goal #{goal.id} {goal.title!r}: purged (irreversible)")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("goal", aliases=["g"], help="Goal operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a Goal")
    add_placement_argument(p_add)
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

    p_list = sub.add_parser("list", help="List Goals, everywhere by default (or one context and its sub-contexts)")
    p_list.add_argument("--status", choices=[s.value for s in GoalStatus])
    add_context_filter_argument(p_list)
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser("search", help="Removed -- use top-level `kb search` instead")
    p_search.add_argument("query", nargs="*", help="Ignored -- use `kb search` instead")
    p_search.set_defaults(func=cmd_search_deprecated)

    p_delete = sub.add_parser("delete", help="Soft-delete a Goal (reversible, see restore)")
    p_delete.add_argument("id", type=int)
    p_delete.set_defaults(func=cmd_delete)

    p_restore = sub.add_parser("restore", help="Undo a soft delete on a Goal")
    p_restore.add_argument("id", type=int)
    p_restore.set_defaults(func=cmd_restore)

    p_purge = sub.add_parser("purge", help="Permanently delete a Goal (irreversible)")
    p_purge.add_argument("id", type=int)
    p_purge.add_argument("--force-delete-links", action="store_true", help="Also delete any EntityLinks pointing at it")
    p_purge.set_defaults(func=cmd_purge)
