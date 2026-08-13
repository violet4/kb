"""Report on kb's own CLI usage/errors -- see CliInvocation in models.py. Makes CLI friction
(a confusing error, a command that keeps failing the same way) queryable on demand instead of
depending on it being reported by hand each time it's hit."""

import argparse
from collections import Counter
from datetime import timedelta

from sqlalchemy import select

from base import _now
from models import CliInvocation


def cmd_errors(args: argparse.Namespace) -> None:
    since = _now() - timedelta(days=args.days)
    rows = args.session.scalars(
        select(CliInvocation).where(CliInvocation.created_at >= since, CliInvocation.success.is_(False))
    ).all()
    total = args.session.scalars(select(CliInvocation).where(CliInvocation.created_at >= since)).all()

    print(f"Last {args.days}d: {len(total)} invocation(s), {len(rows)} error(s)")
    if not total:
        return
    rate = 100 * len(rows) / len(total)
    print(f"Error rate: {rate:.1f}%")
    if not rows:
        return

    print("\nTop failing commands (by first word/subcommand):")
    command_counts = Counter(r.command.split()[0] if r.command.split() else "" for r in rows)
    for cmd, count in command_counts.most_common(args.top):
        print(f"  {count:>3}  {cmd}")

    print("\nTop recurring error messages:")
    error_counts = Counter(r.error for r in rows if r.error)
    for msg, count in error_counts.most_common(args.top):
        short = msg if len(msg) <= 100 else msg[:97] + "..."
        print(f"  {count:>3}  {short}")


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("stats", help="Report on kb CLI usage/error patterns")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_errors = sub.add_parser("errors", help="Show recent CLI error patterns (default view)")
    p_errors.add_argument("--days", type=int, default=7, help="Look back this many days (default: 7)")
    p_errors.add_argument("--top", type=int, default=10, help="Show top N entries per section (default: 10)")
    p_errors.set_defaults(func=cmd_errors)
