"""Report on kb's own CLI usage/errors -- see CliInvocation in models.py. Makes CLI friction
(a confusing error, a command that keeps failing the same way) queryable on demand instead of
depending on it being reported by hand each time it's hit."""

import argparse
import io
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from cli_instrumentation.stats import add_stats_subparser

from base import _now
from models import CliInvocation, SessionFactory

from kb_cli import instruction
from kb_cli.bare_text import BARE_INSTRUCTIONS
from kb_cli.usage import add_usage_subparser

# Anthropic publishes no offline tokenizer (unlike OpenAI's tiktoken) -- the only accurate
# token count is the live count_tokens API endpoint, which this command deliberately does not
# call (see kb Note #148: no network dependency for a lightweight local utility). This is a
# chars-per-token heuristic for dense English prose/markdown; it can be off by roughly 15-20%
# against the real tokenizer, so every output using it is labeled "approximate".
_CHARS_PER_TOKEN = 4.0

# Sonnet 5 introductory input-token pricing, in effect through 2026-08-31 (see the claude-api
# skill's cached model table, refreshed 2026-06-24) -- $/million tokens. This block is
# read-only session bootstrap content, so only input pricing is relevant, not output. A
# snapshot in time, not a durable fact; pass --input-price for a different/current rate.
_DEFAULT_INPUT_PRICE_PER_M = 2.00

_KB_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "kb"


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


def _rows_from_session(session: Session, since: datetime) -> list[dict[str, Any]]:
    """Query logic split out from _fetch_instrumentation_rows so it's testable against
    tests/conftest.py's in-memory db_session fixture, without needing the real on-disk DB
    _fetch_instrumentation_rows itself talks to via SessionFactory."""
    rows = session.scalars(select(CliInvocation).where(CliInvocation.created_at >= since)).all()
    return [
        {
            "command": r.command,
            "subcommand": r.subcommand,
            "success": r.success,
            "error": r.error,
            "duration_ms": r.duration_ms,
        }
        for r in rows
    ]


def _fetch_instrumentation_rows(since: datetime) -> list[dict[str, Any]]:
    """cli_instrumentation.stats.add_stats_subparser's fetch_rows callback -- a fresh,
    short-lived session, same rationale as _record_invocation in the `kb` script itself:
    an unrelated failed command elsewhere shouldn't leave a stale transaction for this
    read-only report to inherit."""
    session = SessionFactory()
    try:
        return _rows_from_session(session, since)
    finally:
        session.close()


def _session_header_text(session: Session) -> str:
    """The exact text printed by `kb i show root; kb` -- the mandatory session-bootstrap
    block every Claude Code session pays for at least once (see ~/.claude/CLAUDE.md's
    first-tool-call rule, and kb Note #148 for why this is estimated rather than measured
    via the live count_tokens API). Captured in-process via redirect_stdout rather than
    shelling out to a `kb` subprocess -- same DB session, no second interpreter/DB connection
    spun up just to capture stdout."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        root = instruction._resolve_ref(session, "root")
        if root is None:
            raise RuntimeError("Instruction tree has no root node -- run `kb i root --set TITLE` first")
        instruction._print_node(session, root, show_body=True)
        print(f"\nThis routing guide is printed by {_KB_SCRIPT_PATH} (bare `kb`, no subcommand).\n")
        print(BARE_INSTRUCTIONS, end="")
    return buf.getvalue()


def cmd_session_header_cost(args: argparse.Namespace) -> None:
    text = _session_header_text(args.session)
    chars = len(text)
    tokens = chars / _CHARS_PER_TOKEN

    input_price = args.input_price if args.input_price is not None else _DEFAULT_INPUT_PRICE_PER_M
    cost = tokens / 1_000_000 * input_price

    print(f"`kb i show root; kb` session-header text: {chars:,} chars")
    print(f"Approximate tokens (chars / {_CHARS_PER_TOKEN:g}): {tokens:,.0f}")
    print(
        f"Approximate cost at ${input_price:.2f}/1M input tokens: ${cost:.4f}"
        + ("  (Sonnet 5 intro pricing snapshot)" if args.input_price is None else "")
    )
    print(
        "\nApproximate only -- Anthropic publishes no offline tokenizer, so this uses a "
        f"chars/{_CHARS_PER_TOKEN:g} heuristic (~15-20% error vs. the real tokenizer), not "
        "the live count_tokens API. Pass --input-price for a different/current rate."
    )


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("stats", help="Report on kb CLI usage/error patterns")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_errors = sub.add_parser("errors", help="Show recent CLI error patterns (default view)")
    p_errors.add_argument("--days", type=int, default=7, help="Look back this many days (default: 7)")
    p_errors.add_argument("--top", type=int, default=10, help="Show top N entries per section (default: 10)")
    p_errors.set_defaults(func=cmd_errors)

    p_header = sub.add_parser(
        "session-header-cost", help="Approximate token count/cost of the `kb i show root; kb` session-bootstrap text"
    )
    p_header.add_argument(
        "--input-price",
        type=float,
        default=None,
        metavar="USD_PER_M",
        help=f"$/1M input tokens (default: today's Sonnet 5 intro snapshot, ${_DEFAULT_INPUT_PRICE_PER_M:.2f})",
    )
    p_header.set_defaults(func=cmd_session_header_cost)

    add_usage_subparser(sub)
    add_stats_subparser(sub, fetch_rows=_fetch_instrumentation_rows)
