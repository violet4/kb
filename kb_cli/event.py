"""Event operations."""

import argparse
import sys
from datetime import datetime, timezone
from typing import Optional, Sequence

from dateutil.parser import parse as parse_datetime
from sqlalchemy import select

from context import creation_context, resolve_context
from models import Event

from kb_cli._util import (
    apply_context_or_tag_update,
    apply_updates,
    print_fields,
    print_links,
    print_table,
    resolve_text_arg,
    scope_to_context,
)
from kb_cli.search import cmd_search_deprecated


def _parse_starts_at(value: str, is_all_day: bool = False) -> datetime:
    """Accepts a bare date ("2026-10-15") or a full ISO-ish datetime ("2026-10-15 14:30") --
    dateutil.parser handles both without a caller-specified format string. A naive result
    (no offset/zone in the input) is assumed local time, then converted to UTC for storage,
    matching every other DateTime(timezone=True) column's _now()-derived UTC convention.

    is_all_day bypasses that local->UTC conversion entirely and stores the given calendar
    date as UTC midnight -- an all-day event's date must round-trip to the same date it was
    entered as (Event's class docstring: "stored as midnight UTC and never displayed with a
    clock time"), which local-time conversion breaks: "2026-10-15" entered in a negative-UTC-
    offset zone would convert to a UTC instant still on 2026-10-15 but past midnight, or in a
    positive-offset zone could roll back to 2026-10-14 UTC entirely, corrupting the date."""
    dt: datetime = parse_datetime(value)
    if is_all_day:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc)


def _event_fields(event: Event) -> list[tuple[str, object]]:
    starts_at = event.starts_at.replace(tzinfo=timezone.utc) if event.starts_at.tzinfo is None else event.starts_at
    return [
        ("id", event.id),
        ("title", event.title),
        ("starts_at", starts_at.date().isoformat() if event.is_all_day else starts_at.isoformat()),
        ("all_day", event.is_all_day),
        ("recurrence", event.recurrence),
        ("context", event.context.name if event.context else None),
        ("tag", event.tag.name if event.tag else None),
        ("notes", event.notes),
        ("created_at", event.created_at.replace(tzinfo=timezone.utc)),
        ("updated_at", event.updated_at.replace(tzinfo=timezone.utc)),
    ]


def cmd_show(args: argparse.Namespace) -> None:
    event = args.session.get(Event, args.id)
    if event is None:
        print(f"Event #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    print_fields(_event_fields(event))
    next_occ = event.next_occurrence()
    print(f"next_occurrence: {next_occ.isoformat() if next_occ else 'none (past, non-recurring)'}")
    print_links(args.session, "Event", event.id)


def cmd_list(args: argparse.Namespace) -> None:
    context = resolve_context(args.session, args.context) if args.context else None
    contexts = scope_to_context(args.session, context) if not args.all else None
    events: Sequence[Event] = Event.active(
        args.session, contexts=contexts, include_no_context=True if contexts is not None else False
    )
    upcoming = [(e, e.next_occurrence()) for e in events]
    upcoming = [(e, occ) for e, occ in upcoming if occ is not None or args.all]
    upcoming.sort(key=lambda pair: pair[1] or datetime.max.replace(tzinfo=timezone.utc))
    if not upcoming:
        print("No upcoming events.")
        return
    rows = []
    for e, occ in upcoming:
        when = "(past)" if occ is None else (occ.date().isoformat() if e.is_all_day else occ.isoformat())
        rows.append([str(e.id), e.title, when, e.recurrence or "", e.context.name if e.context else ""])
    print_table(["id", "title", "next", "recurrence", "context"], rows)


def cmd_add(args: argparse.Namespace) -> None:
    title = resolve_text_arg(args.title)

    nearest = Event.search(args.session, title, limit=1)
    if nearest:
        e, dist = nearest[0]
        print(f"Nearest existing Event: #{e.id} {e.title!r} (dist={dist:.3f})", file=sys.stderr)

    event = Event.create(
        args.session,
        title,
        _parse_starts_at(args.starts_at, is_all_day=args.all_day),
        context=creation_context(args),
        is_all_day=args.all_day,
        recurrence=args.recurrence,
        notes=resolve_text_arg(args.notes) if args.notes else args.notes,
    )
    args.session.commit()
    print_fields(_event_fields(event))


def cmd_update(args: argparse.Namespace) -> None:
    existing = args.session.get(Event, args.id)
    if existing is None:
        print(f"Event #{args.id}: not found", file=sys.stderr)
        sys.exit(1)
    is_all_day = args.all_day if args.all_day is not None else existing.is_all_day
    if args.starts_at:
        starts_at = _parse_starts_at(args.starts_at, is_all_day=is_all_day)
    elif args.all_day is True and not existing.is_all_day:
        # Toggling on --all-day without also re-supplying starts_at: renormalize the
        # existing instant to midnight UTC on its own date, otherwise is_all_day=True
        # would combine with a non-midnight starts_at, breaking the "all-day means
        # midnight UTC" invariant next_occurrence()/display both rely on.
        starts_at = existing.starts_at.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        starts_at = None
    event = apply_updates(
        args.session,
        Event,
        args.id,
        "Event",
        {
            "title": resolve_text_arg(args.title) if args.title else args.title,
            "starts_at": starts_at,
            "is_all_day": args.all_day,
            "recurrence": args.recurrence,
            "notes": resolve_text_arg(args.notes) if args.notes else args.notes,
        },
    )
    apply_context_or_tag_update(args.session, event, args.new_context, args.new_tag)
    args.session.commit()
    print(event)


def cmd_delete(args: argparse.Namespace) -> None:
    """Two-stage confirm (--yes required), matching Daily/Todo/etc. -- see daily.py's
    cmd_delete for the full reasoning (no reliable interactive stdin in an agent harness)."""
    events = []
    missing = []
    for event_id in args.ids:
        event = args.session.get(Event, event_id)
        if event is None:
            missing.append(event_id)
        else:
            events.append(event)
    for event_id in missing:
        print(f"Event #{event_id}: not found", file=sys.stderr)
    if not events:
        return
    if not args.yes:
        print("This would permanently delete:")
        for event in events:
            print(f"  #{event.id} {event.title!r}")
        print("\nRe-run this same command with --yes to actually delete.")
        return
    for event in events:
        print(f"Deleted Event #{event.id} {event.title!r}")
        args.session.delete(event)
    args.session.commit()


def cmd_reembed(args: argparse.Namespace) -> None:
    from embed import model_name

    events = args.session.scalars(select(Event)).all()
    if not events:
        print("No events to reembed.")
        return
    print(f"Reembedding {len(events)} events with model '{model_name()}'...")
    for i, event in enumerate(events, 1):
        event.reembed()
        print(f"  [{i}/{len(events)}] {event.title!r}")
    args.session.commit()
    print("Done.")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("event", aliases=["ev", "events"], help="Event (calendar) operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show Event details")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_show)

    p_list = sub.add_parser("list", help="List upcoming events, soonest first")
    p_list.add_argument("--context", help="Scope to this context's subtree")
    p_list.add_argument("--all", action="store_true", help="Show every event, including past/unscoped")
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Add an Event")
    p_add.add_argument("title")
    p_add.add_argument(
        "starts_at",
        help="Date or datetime, e.g. '2026-10-15' or '2026-10-15 14:30' (naive input is treated as local time)",
    )
    p_add.add_argument("--all-day", dest="all_day", action="store_true", help="Date-only, no meaningful time-of-day")
    p_add.add_argument(
        "--recurrence",
        help="RFC 5545 RRULE string, e.g. 'FREQ=YEARLY;BYMONTH=7;BYMONTHDAY=23' or 'FREQ=WEEKLY;BYDAY=MO,WE,FR'",
    )
    p_add.add_argument("--notes")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update fields on an existing Event")
    p_update.add_argument("id", type=int)
    p_update.add_argument("--title")
    p_update.add_argument("--starts-at", dest="starts_at")
    p_update.add_argument("--all-day", dest="all_day", action="store_true", default=None)
    p_update.add_argument("--recurrence", help="RFC 5545 RRULE string; pass '' to clear")
    p_update.add_argument("--notes")
    p_update.add_argument("--context", dest="new_context", metavar="NAME")
    p_update.add_argument("--tag", dest="new_tag", metavar="NAME", help="Address by Tag instead of context")
    p_update.set_defaults(func=cmd_update)

    p_delete = sub.add_parser(
        "delete", help="Permanently delete Event(s) (e.g. an accidental duplicate) -- requires --yes to confirm"
    )
    p_delete.add_argument("ids", nargs="+", type=int)
    p_delete.add_argument("--yes", action="store_true", help="Actually perform the delete.")
    p_delete.set_defaults(func=cmd_delete)

    p_search = sub.add_parser("search", help="Removed -- use top-level `kb search` instead")
    p_search.add_argument("query", nargs="*", help="Ignored -- use `kb search` instead")
    p_search.set_defaults(func=cmd_search_deprecated)

    p_reembed = sub.add_parser("reembed", help="Recompute embeddings for all events")
    p_reembed.set_defaults(func=cmd_reembed)
