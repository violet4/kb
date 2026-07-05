"""Goal operations."""
import sys

from context import resolve_context
from models import Goal, GoalStatus, Journal, sess

from kb_cli._util import add_history_arg, print_journal_history


def cmd_add(args):
    context = resolve_context(args.context)
    goal = Goal.create(args.title, description=args.description, context=context, notes=args.notes)
    sess.commit()
    print(goal)


def cmd_show(args):
    for i, goal_id in enumerate(args.ids):
        if i > 0:
            print()
        goal = sess.get(Goal, goal_id)
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

        print_journal_history(Journal, "Goal", goal.id, args.history, f"journal show Goal {goal.id} or kb goal show {goal.id} --history [N]")


def _set_status(ids, status, verb):
    for goal_id in ids:
        goal = sess.get(Goal, goal_id)
        if goal is None:
            print(f"Goal #{goal_id}: not found", file=sys.stderr)
            continue
        goal.status = status
        print(f"Goal #{goal_id}: {goal.title!r} -> {verb}")
    sess.commit()


def cmd_complete(args):
    _set_status(args.ids, GoalStatus.COMPLETED, "completed")


def cmd_abandon(args):
    _set_status(args.ids, GoalStatus.ABANDONED, "abandoned")


def cmd_hold(args):
    _set_status(args.ids, GoalStatus.ON_HOLD, "on hold")


def cmd_reactivate(args):
    _set_status(args.ids, GoalStatus.ACTIVE, "active")


def add_subparser(subparsers):
    parser = subparsers.add_parser("goal", help="Goal operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a Goal")
    p_add.add_argument("title")
    p_add.add_argument("--description")
    p_add.add_argument("--notes")
    p_add.add_argument("--context", metavar="NAME", help="Act in context NAME for this command only")
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
