"""Daily operations."""
import sys

from sqlalchemy import select

from context import resolve_context
from models import Daily, sess

from kb_cli._util import print_fields


def cmd_show(args):
    daily = sess.get(Daily, args.id)
    if daily is None:
        print(f"Daily #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    print_fields([
        ("id", daily.id),
        ("description", daily.description),
        ("active", daily.is_active),
        ("context", daily.context.name if daily.context else None),
        ("location", daily.location),
        ("reward", daily.reward),
        ("notes", daily.notes),
    ])


def cmd_list(args):
    context = resolve_context(args.context) if args.context else None
    dailies = Daily.active(context=context) if not args.all else sess.scalars(select(Daily)).all()
    if not dailies:
        print("No dailies.")
        return
    for d in dailies:
        marker = "" if d.is_active else " [inactive]"
        print(f"{d!r}{marker}")


def cmd_add(args):
    context = resolve_context(args.context)
    daily = Daily.create(args.description, context=context, location=args.location, reward=args.reward, notes=args.notes)
    sess.commit()
    print(daily)


def cmd_update(args):
    daily = sess.get(Daily, args.id)
    if daily is None:
        print(f"Daily #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    if args.description is not None:
        daily.description = args.description
    if args.location is not None:
        daily.location = args.location
    if args.reward is not None:
        daily.reward = args.reward
    if args.notes is not None:
        daily.notes = args.notes
    if args.context is not None:
        daily.context = resolve_context(args.context)
    sess.commit()
    print(daily)


def cmd_activate(args):
    for daily_id in args.ids:
        daily = sess.get(Daily, daily_id)
        if daily is None:
            print(f"Daily #{daily_id}: not found", file=sys.stderr)
            continue
        daily.is_active = True
        print(f"Daily #{daily_id}: {daily.description!r} -> active")
    sess.commit()


def cmd_deactivate(args):
    for daily_id in args.ids:
        daily = sess.get(Daily, daily_id)
        if daily is None:
            print(f"Daily #{daily_id}: not found", file=sys.stderr)
            continue
        daily.is_active = False
        print(f"Daily #{daily_id}: {daily.description!r} -> inactive")
    sess.commit()


def add_subparser(subparsers):
    parser = subparsers.add_parser("daily", help="Daily operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show Daily details")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_show)

    p_list = sub.add_parser("list", help="List dailies (active by default)")
    p_list.add_argument("--context", metavar="NAME", help="Only show dailies in this context")
    p_list.add_argument("--all", action="store_true", help="Include inactive dailies too")
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Add a Daily")
    p_add.add_argument("description")
    p_add.add_argument("--location")
    p_add.add_argument("--reward")
    p_add.add_argument("--notes")
    p_add.add_argument("--context", metavar="NAME", help="Act in context NAME for this command only")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update fields on an existing Daily")
    p_update.add_argument("id", type=int)
    p_update.add_argument("--description")
    p_update.add_argument("--location")
    p_update.add_argument("--reward")
    p_update.add_argument("--notes")
    p_update.add_argument("--context", metavar="NAME")
    p_update.set_defaults(func=cmd_update)

    p_activate = sub.add_parser("activate", help="Mark Daily(s) active")
    p_activate.add_argument("ids", nargs="+", type=int)
    p_activate.set_defaults(func=cmd_activate)

    p_deactivate = sub.add_parser("deactivate", help="Mark Daily(s) inactive")
    p_deactivate.add_argument("ids", nargs="+", type=int)
    p_deactivate.set_defaults(func=cmd_deactivate)
