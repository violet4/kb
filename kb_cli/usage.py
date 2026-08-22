"""Shared `claude -p /usage` fetch/parse logic -- one implementation behind both
`api/usage_router.py` (the web view) and `kb stats usage` (this module's own CLI command), so
the two never drift on how the CLI's plain-text output is parsed."""

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_SESSION_RE = re.compile(r"Current session:\s*(\d+)%\s*used\s*.*?resets\s*(.+)")
_WEEK_RE = re.compile(r"Current week \(all models\):\s*(\d+)%\s*used\s*.*?resets\s*(.+)")
_RESETS_RE = re.compile(r"^(.+?)\s*\(([^)]+)\)\s*$")

SESSION_PERIOD = timedelta(hours=5)
WEEK_PERIOD = timedelta(days=7)


class UsageFetchError(RuntimeError):
    """Raised when `claude -p /usage` fails to run or its output can't be parsed."""


@dataclass
class Usage:
    session_pct: int
    session_resets: str
    session_resets_at: datetime
    week_pct: int
    week_resets: str
    week_resets_at: datetime


def _parse_resets_at(resets: str) -> datetime:
    """Parses e.g. "Aug 21, 6:19pm (America/Los_Angeles)" into a UTC datetime. The claude
    CLI's output has no year, so the year is inferred as whichever of this-year/next-year
    keeps the reset in the future relative to now in that same timezone."""
    match = _RESETS_RE.match(resets)
    if not match:
        raise ValueError(f"could not parse resets string: {resets!r}")
    when_str, tz_name = match.groups()
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    # The claude CLI drops ":00" on the hour (e.g. "9pm" instead of "9:00pm").
    time_fmt = "%I:%M%p" if ":" in when_str else "%I%p"
    parsed = datetime.strptime(f"{now.year} {when_str}", f"%Y %b %d, {time_fmt}").replace(tzinfo=tz)
    if parsed < now:
        parsed = parsed.replace(year=now.year + 1)
    return parsed.astimezone(ZoneInfo("UTC"))


def fetch_usage() -> Usage:
    try:
        result = subprocess.run(
            ["claude", "-p", "/usage", "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise UsageFetchError(f"claude /usage failed: {e}") from e

    try:
        output = json.loads(result.stdout)["result"]
    except (json.JSONDecodeError, KeyError) as e:
        raise UsageFetchError(f"could not parse claude /usage JSON envelope: {e}") from e

    session_match = _SESSION_RE.search(output)
    week_match = _WEEK_RE.search(output)
    if not session_match or not week_match:
        raise UsageFetchError(f"could not parse claude /usage output: {output!r}")

    session_resets = session_match.group(2).strip()
    week_resets = week_match.group(2).strip()
    try:
        session_resets_at = _parse_resets_at(session_resets)
        week_resets_at = _parse_resets_at(week_resets)
    except (ValueError, KeyError) as e:
        raise UsageFetchError(f"could not parse reset timestamp: {e}") from e

    return Usage(
        session_pct=int(session_match.group(1)),
        session_resets=session_resets,
        session_resets_at=session_resets_at,
        week_pct=int(week_match.group(1)),
        week_resets=week_resets,
        week_resets_at=week_resets_at,
    )


def _format_bar(label: str, pct: int, resets_at: datetime, period: timedelta, width: int = 30) -> str:
    now = datetime.now(resets_at.tzinfo)
    remaining = max(timedelta(0), resets_at - now)
    elapsed = max(timedelta(0), min(period, period - remaining))
    estimated_pct = 100 * elapsed / period

    filled = round(width * min(100, max(0, pct)) / 100)
    marker_pos = min(width - 1, round(width * min(100, max(0, estimated_pct)) / 100))
    bar = list("#" * filled + "-" * (width - filled))
    bar[marker_pos] = "|" if bar[marker_pos] == "-" else "!"
    bar_str = "".join(bar)

    total_minutes = int(remaining.total_seconds() // 60)
    days, rem_minutes = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem_minutes, 60)
    if days > 0:
        countdown = f"{days}d {hours}h {minutes:02d}m"
    elif hours > 0:
        countdown = f"{hours}h {minutes:02d}m"
    else:
        countdown = f"{minutes}m"

    local_resets_at = resets_at.astimezone()
    return (
        f"{label:<24} [{bar_str}] {pct:>3}% used  ·  {countdown} left"
        f"  ·  resets {local_resets_at.strftime('%b %d, %-I:%M%p')}"
        f"  ·  est. pace {estimated_pct:.0f}%"
    )


def cmd_usage(args: argparse.Namespace) -> None:
    try:
        usage = fetch_usage()
    except UsageFetchError as e:
        raise SystemExit(str(e))

    print(_format_bar("Current session", usage.session_pct, usage.session_resets_at, SESSION_PERIOD))
    print(_format_bar("Current week (all models)", usage.week_pct, usage.week_resets_at, WEEK_PERIOD))
    print("\n`|`/`!` marks estimated pace -- where usage would be if spent evenly across the period.")


def add_usage_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    """Registers `usage` onto an existing subparsers group -- called from stats.py's own
    add_subparser so this lives under `kb stats usage`, not as its own top-level noun."""
    parser = sub.add_parser("usage", help="Show Claude usage (mirrors the web /usage page)")
    parser.set_defaults(func=cmd_usage)
