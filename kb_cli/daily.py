"""Daily operations."""

import argparse
import sys
from typing import Sequence

from sqlalchemy import select

from context import resolve_context
from models import Daily, DailyTier

from kb_cli._util import print_fields, print_table


def cmd_show(args: argparse.Namespace) -> None:
    daily = args.session.get(Daily, args.id)
    if daily is None:
        print(f"Daily #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    print_fields(
        [
            ("id", daily.id),
            ("description", daily.description),
            ("active", daily.is_active),
            ("domain", daily.domain),
            ("tier", daily.tier.value),
            ("recurrence", daily.recurrence),
            ("show_after_hour", daily.show_after_hour),
            ("next_due_date", daily.next_due_date.isoformat()),
            ("context", daily.context.name if daily.context else None),
            ("location", daily.location),
            ("reward", daily.reward),
            ("notes", daily.notes),
        ]
    )


def cmd_list(args: argparse.Namespace) -> None:
    dailies: Sequence[Daily]
    if args.all:
        q = select(Daily)
        if args.domain:
            q = q.where(Daily.domain == args.domain)
        if args.tier:
            q = q.where(Daily.tier == DailyTier(args.tier))
        dailies = args.session.scalars(q).all()
    else:
        domain = args.domain
        tier = DailyTier(args.tier) if args.tier else None
        dailies = Daily.due(args.session, domain=domain, tier=tier)
    if not dailies:
        print("No dailies due." if not args.all else "No dailies.")
        return
    dailies = sorted(dailies, key=lambda d: d.next_due_date)
    rows = []
    for d in dailies:
        status = "" if d.is_active else "inactive"
        rows.append(
            [
                str(d.id),
                d.description,
                d.tier.value,
                d.recurrence,
                d.next_due_date.isoformat(),
                str(d.show_after_hour) if d.show_after_hour is not None else "",
                status,
            ]
        )
    print_table(["id", "description", "tier", "recurrence", "next due", "show after", "status"], rows)


def cmd_complete(args: argparse.Namespace) -> None:
    for daily_id in args.ids:
        daily = args.session.get(Daily, daily_id)
        if daily is None:
            print(f"Daily #{daily_id}: not found", file=sys.stderr)
            continue
        daily.complete(args.session)
        print(f"Daily #{daily_id}: {daily.description!r} -> completed, next due {daily.next_due_date.isoformat()}")
    args.session.commit()


def cmd_catch_up(args: argparse.Namespace) -> None:
    for daily_id in args.ids:
        daily = args.session.get(Daily, daily_id)
        if daily is None:
            print(f"Daily #{daily_id}: not found", file=sys.stderr)
            continue
        daily.catch_up(args.session)
        print(f"Daily #{daily_id}: {daily.description!r} -> caught up, next due {daily.next_due_date.isoformat()}")
    args.session.commit()


def cmd_add(args: argparse.Namespace) -> None:
    daily = Daily.create(
        args.session,
        args.description,
        context=args.context,
        domain=args.domain,
        tier=DailyTier(args.tier),
        recurrence=args.recurrence,
        show_after_hour=args.show_after_hour,
        location=args.location,
        reward=args.reward,
        notes=args.notes,
    )
    args.session.commit()
    print(daily)


def cmd_update(args: argparse.Namespace) -> None:
    daily = args.session.get(Daily, args.id)
    if daily is None:
        print(f"Daily #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    if args.description is not None:
        daily.description = args.description
    if args.domain is not None:
        daily.domain = args.domain
    if args.tier is not None:
        daily.tier = DailyTier(args.tier)
    if args.recurrence is not None:
        daily.recurrence = args.recurrence
    if args.show_after_hour is not None:
        daily.show_after_hour = args.show_after_hour
    if args.location is not None:
        daily.location = args.location
    if args.reward is not None:
        daily.reward = args.reward
    if args.notes is not None:
        daily.notes = args.notes
    if args.new_context is not None:
        daily.context = resolve_context(args.session, args.new_context)
    args.session.commit()
    print(daily)


def cmd_activate(args: argparse.Namespace) -> None:
    for daily_id in args.ids:
        daily = args.session.get(Daily, daily_id)
        if daily is None:
            print(f"Daily #{daily_id}: not found", file=sys.stderr)
            continue
        daily.is_active = True
        print(f"Daily #{daily_id}: {daily.description!r} -> active")
    args.session.commit()


def cmd_deactivate(args: argparse.Namespace) -> None:
    for daily_id in args.ids:
        daily = args.session.get(Daily, daily_id)
        if daily is None:
            print(f"Daily #{daily_id}: not found", file=sys.stderr)
            continue
        daily.is_active = False
        print(f"Daily #{daily_id}: {daily.description!r} -> inactive")
    args.session.commit()


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
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
    p_add.add_argument(
        "--recurrence",
        default="daily",
        help="'daily' (default), 'every:N', 'weekly:MON'..'SUN', or 'monthly:D' (day 1-28)",
    )
    p_add.add_argument(
        "--show-after-hour", type=int, dest="show_after_hour", help="Hide until this local hour (0-23), e.g. 19 for 7pm"
    )
    p_add.add_argument("--location")
    p_add.add_argument("--reward")
    p_add.add_argument("--notes")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update fields on an existing Daily")
    p_update.add_argument("id", type=int)
    p_update.add_argument("--description")
    p_update.add_argument("--domain")
    p_update.add_argument("--tier", choices=[t.value for t in DailyTier])
    p_update.add_argument("--recurrence", help="'daily', 'every:N', 'weekly:MON'..'SUN', or 'monthly:D' (day 1-28)")
    p_update.add_argument(
        "--show-after-hour", type=int, dest="show_after_hour", help="Hide until this local hour (0-23), e.g. 19 for 7pm"
    )
    p_update.add_argument("--location")
    p_update.add_argument("--reward")
    p_update.add_argument("--notes")
    p_update.add_argument("--context", dest="new_context", metavar="NAME")
    p_update.set_defaults(func=cmd_update)

    p_complete = sub.add_parser("complete", help="Mark Daily(s) completed for the current day-boundary window")
    p_complete.add_argument("ids", nargs="+", type=int)
    p_complete.set_defaults(func=cmd_complete)

    p_catch_up = sub.add_parser(
        "catch-up", help="Advance overdue Daily(s) to their next non-overdue occurrence, without marking them done"
    )
    p_catch_up.add_argument("ids", nargs="+", type=int)
    p_catch_up.set_defaults(func=cmd_catch_up)

    p_activate = sub.add_parser("activate", help="Mark Daily(s) active")
    p_activate.add_argument("ids", nargs="+", type=int)
    p_activate.set_defaults(func=cmd_activate)

    p_deactivate = sub.add_parser("deactivate", help="Mark Daily(s) inactive")
    p_deactivate.add_argument("ids", nargs="+", type=int)
    p_deactivate.set_defaults(func=cmd_deactivate)
