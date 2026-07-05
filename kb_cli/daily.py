"""Daily operations."""
import sys

from sqlalchemy import select

from context import resolve_context
from models import Daily, DailyTier, sess

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
        ("domain", daily.domain),
        ("tier", daily.tier.value),
        ("last_completed_at", daily.last_completed_at.strftime("%Y-%m-%d %H:%M") if daily.last_completed_at else None),
        ("context", daily.context.name if daily.context else None),
        ("location", daily.location),
        ("reward", daily.reward),
        ("notes", daily.notes),
    ])


def cmd_list(args):
    if args.all:
        dailies = sess.scalars(select(Daily)).all()
    else:
        domain = args.domain
        tier = DailyTier(args.tier) if args.tier else None
        dailies = Daily.due(domain=domain, tier=tier)
    if not dailies:
        print("No dailies due." if not args.all else "No dailies.")
        return
    for d in dailies:
        marker = "" if d.is_active else " [inactive]"
        print(f"{d!r}{marker}")


def cmd_complete(args):
    for daily_id in args.ids:
        daily = sess.get(Daily, daily_id)
        if daily is None:
            print(f"Daily #{daily_id}: not found", file=sys.stderr)
            continue
        daily.complete()
        print(f"Daily #{daily_id}: {daily.description!r} -> completed for today")
    sess.commit()


def cmd_add(args):
    context = resolve_context(args.context)
    daily = Daily.create(args.description, context=context, domain=args.domain, tier=DailyTier(args.tier),
                         location=args.location, reward=args.reward, notes=args.notes)
    sess.commit()
    print(daily)


def cmd_update(args):
    daily = sess.get(Daily, args.id)
    if daily is None:
        print(f"Daily #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    if args.description is not None:
        daily.description = args.description
    if args.domain is not None:
        daily.domain = args.domain
    if args.tier is not None:
        daily.tier = DailyTier(args.tier)
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

    p_list = sub.add_parser("list", help="List dailies due today (default: irl+critical only, per --domain/--tier)")
    p_list.add_argument("--domain", help="Filter to this domain, e.g. 'irl' or 'pg'")
    p_list.add_argument("--tier", choices=[t.value for t in DailyTier], help="Filter to this tier")
    p_list.add_argument("--all", action="store_true", help="Show every daily regardless of domain/tier/completion")
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Add a Daily")
    p_add.add_argument("description")
    p_add.add_argument("--domain", default="irl", help="'irl' (default) or 'pg'")
    p_add.add_argument("--tier", default="critical", choices=[t.value for t in DailyTier])
    p_add.add_argument("--location")
    p_add.add_argument("--reward")
    p_add.add_argument("--notes")
    p_add.add_argument("--context", metavar="NAME", help="Act in context NAME for this command only")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update fields on an existing Daily")
    p_update.add_argument("id", type=int)
    p_update.add_argument("--description")
    p_update.add_argument("--domain")
    p_update.add_argument("--tier", choices=[t.value for t in DailyTier])
    p_update.add_argument("--location")
    p_update.add_argument("--reward")
    p_update.add_argument("--notes")
    p_update.add_argument("--context", metavar="NAME")
    p_update.set_defaults(func=cmd_update)

    p_complete = sub.add_parser("complete", help="Mark Daily(s) completed for the current day-boundary window")
    p_complete.add_argument("ids", nargs="+", type=int)
    p_complete.set_defaults(func=cmd_complete)

    p_activate = sub.add_parser("activate", help="Mark Daily(s) active")
    p_activate.add_argument("ids", nargs="+", type=int)
    p_activate.set_defaults(func=cmd_activate)

    p_deactivate = sub.add_parser("deactivate", help="Mark Daily(s) inactive")
    p_deactivate.add_argument("ids", nargs="+", type=int)
    p_deactivate.set_defaults(func=cmd_deactivate)
