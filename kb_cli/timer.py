"""Timer operations. This CLI only writes/reads Timer rows -- the actual counting
down and alerting is the job of the (not-yet-built) timer daemon; see the
stateless `timer` script (~/bin/timer) for one-off terminal countdowns instead."""

import argparse
import sys
from datetime import datetime, timezone

from context import warn_ambient_context
from context_tree import render_context_tree
from models import Tag, Timer, TimerStatus

from kb_cli._util import get_by_name


def _parse_duration(raw: str) -> int:
    if ":" in raw:
        parts = raw.split(":")
        try:
            if len(parts) == 2:
                m, s = int(parts[0]), int(parts[1])
                return m * 60 + s
            elif len(parts) == 3:
                h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
                return h * 3600 + m * 60 + s
        except ValueError:
            pass
        raise SystemExit(f"duration: could not parse {raw!r} (use M:SS, H:MM:SS, or seconds)")
    try:
        val = int(raw)
    except ValueError:
        raise SystemExit(f"duration: could not parse {raw!r} (use M:SS, H:MM:SS, or seconds)")
    if val <= 0:
        raise SystemExit("duration: must be positive")
    return val


def cmd_add(args: argparse.Namespace) -> None:
    if args.tag and args.context_explicit:
        print("--tag and --context are mutually exclusive", file=sys.stderr)
        sys.exit(2)
    duration = _parse_duration(args.duration)
    tag = get_by_name(args.session, Tag, args.tag) if args.tag else None
    timer = Timer.create(
        args.session,
        duration,
        label=args.label,
        context=None if tag else args.context,
        tag=tag,
        repeat_count=args.repeat,
    )
    args.session.commit()
    if not tag:
        warn_ambient_context(args, "Timer")
    print(timer)


def cmd_list(args: argparse.Namespace) -> None:
    timers = Timer.active(args.session)
    if not timers:
        print("No active timers.")
        return
    now = datetime.now(timezone.utc)
    for t in timers:
        remaining = max(0, int((t.ends_at - now).total_seconds()))
        print(f"{t!r} ({remaining}s remaining)")


def cmd_cancel(args: argparse.Namespace) -> None:
    for timer_id in args.ids:
        timer = args.session.get(Timer, timer_id)
        if timer is None:
            print(f"Timer #{timer_id}: not found", file=sys.stderr)
            continue
        timer.cancel()
        print(f"Timer #{timer_id}: cancelled")
    args.session.commit()


def cmd_tree(args: argparse.Namespace) -> None:
    """Render active Timers nested under the Context tree, tree(1)-style -- see
    `kb todo tree` for the shared rendering logic this reuses."""
    timers = Timer.active(args.session)
    now = datetime.now(timezone.utc)

    def line_for(t: Timer) -> str:
        remaining = max(0, int((t.ends_at - now).total_seconds()))
        label_str = f" {t.label}" if t.label else ""
        return f"timer#{t.id}{label_str} ({remaining}s remaining)"

    unplaced = render_context_tree(args.session, timers, line_for)
    if unplaced:
        print(f"\n({len(unplaced)} timer(s) with no context/tag -- see kb timer list)")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("timer", help="Timer operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a Timer")
    p_add.add_argument("duration", help="M:SS, H:MM:SS, or seconds")
    p_add.add_argument("--label")
    p_add.add_argument(
        "--repeat", type=int, metavar="N", help="Total number of runs (omit = once, 0 = infinite, N = N times)"
    )
    p_add.add_argument("--tag", help="Address by Tag instead of context (mutually exclusive with the global --context)")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List active Timers")
    p_list.set_defaults(func=cmd_list)

    p_cancel = sub.add_parser("cancel", help="Cancel Timer(s)")
    p_cancel.add_argument("ids", nargs="+", type=int)
    p_cancel.set_defaults(func=cmd_cancel)

    p_tree = sub.add_parser("tree", help="Render active Timers nested under the Context tree")
    p_tree.set_defaults(func=cmd_tree)
