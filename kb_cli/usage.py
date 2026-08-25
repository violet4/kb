"""Shared `claude -p /usage` fetch/parse logic -- one implementation behind both
`api/usage_router.py` (the web view) and `kb stats usage` (this module's own CLI command), so
the two never drift on how the CLI's plain-text output is parsed."""

import argparse
import fcntl
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_SESSION_RE = re.compile(r"Current session:\s*(\d+)%\s*used\s*.*?resets\s*(.+)")
_WEEK_RE = re.compile(r"Current week \(all models\):\s*(\d+)%\s*used\s*.*?resets\s*(.+)")
_RESETS_RE = re.compile(r"^(.+?)\s*\(([^)]+)\)\s*$")

SESSION_PERIOD = timedelta(hours=5)
WEEK_PERIOD = timedelta(days=7)

# A fixed path (not per-process) so every caller -- concurrent web requests within the
# server, and separate `kb stats usage` CLI invocations -- converges on the same lock/cache
# file. A caller arriving while another is already mid-fetch blocks on the flock, then reads
# whatever the winner just wrote, instead of shelling out to `claude -p /usage` a second time.
_CACHE_PATH = Path(tempfile.gettempdir()) / "kb-usage-fetch.json"
_LOCK_PATH = Path(tempfile.gettempdir()) / "kb-usage-fetch.lock"

# A result already in flight counts as fresh for any caller that arrives while the flock is
# held; this only guards the short window after the lock is released, in case two callers
# start close enough together that the second acquires the lock just after the first wrote.
_CACHE_MAX_AGE = timedelta(seconds=5)


class UsageFetchError(RuntimeError):
    """Raised when `claude -p /usage` fails to run or its output can't be parsed."""


@dataclass
class Usage:
    """`raw_text` is set instead of the bar fields when `claude -p /usage`'s output doesn't
    match the session/week bar format this module knows how to parse (e.g. the no-usage-yet
    "behaviors contributing to your limits" summary) -- callers render that text as-is rather
    than erroring out, since the underlying data is still meaningful, just shaped differently."""

    session_pct: int | None = None
    session_resets: str | None = None
    session_resets_at: datetime | None = None
    week_pct: int | None = None
    week_resets: str | None = None
    week_resets_at: datetime | None = None
    raw_text: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "session_pct": self.session_pct,
                "session_resets": self.session_resets,
                "session_resets_at": self.session_resets_at.isoformat() if self.session_resets_at else None,
                "week_pct": self.week_pct,
                "week_resets": self.week_resets,
                "week_resets_at": self.week_resets_at.isoformat() if self.week_resets_at else None,
                "raw_text": self.raw_text,
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> "Usage":
        data = json.loads(raw)
        return cls(
            session_pct=data["session_pct"],
            session_resets=data["session_resets"],
            session_resets_at=(
                datetime.fromisoformat(data["session_resets_at"]) if data["session_resets_at"] else None
            ),
            week_pct=data["week_pct"],
            week_resets=data["week_resets"],
            week_resets_at=datetime.fromisoformat(data["week_resets_at"]) if data["week_resets_at"] else None,
            raw_text=data.get("raw_text"),
        )


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


def _fetch_usage_uncached() -> Usage:
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
        # No usage yet (or some other unrecognized shape) makes `claude -p /usage` print a
        # different summary (subscription blurb + "behaviors contributing to your limits")
        # instead of the session/week bar lines -- pass that text through as-is rather than
        # treating an unfamiliar format as a hard failure.
        return Usage(raw_text=output)

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


def fetch_usage() -> Usage:
    """Single-flighted across every caller (any thread/process on this machine): holds an
    flock for the duration of the underlying `claude -p /usage` call, so a caller that arrives
    while one is already in flight blocks on the lock rather than starting a second redundant
    subprocess, then reads the result the first caller just wrote instead of re-fetching."""
    _LOCK_PATH.touch(exist_ok=True)
    with open(_LOCK_PATH) as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            if _CACHE_PATH.exists():
                age = datetime.now().timestamp() - _CACHE_PATH.stat().st_mtime
                if age <= _CACHE_MAX_AGE.total_seconds():
                    return Usage.from_json(_CACHE_PATH.read_text())

            usage = _fetch_usage_uncached()
            _CACHE_PATH.write_text(usage.to_json())
            return usage
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


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


# A real sample of `claude -p /usage`'s no-usage-yet output (see kb_cli/usage.py's raw_text
# docstring) -- used by `kb stats usage --sample-passthrough` to exercise the raw_text
# passthrough path on demand, since triggering it for real requires an empty 5-hour session
# window, which is impractical to wait for while testing.
_SAMPLE_PASSTHROUGH_TEXT = """\
You are currently using your subscription to power your Claude Code usage

What's contributing to your limits usage?
Approximate, based on local sessions on this machine -- does not include other devices or claude.ai. Behaviors are independent characteristics, not a breakdown.

Last 24h · 1031 requests · 7 sessions
  96% of your usage came from subagent-heavy sessions
  87% of your usage was at >150k context
  Top subagents: fork 5%, general-purpose 1%
  Top MCP servers: chrome-devtools 13%

Last 7d · 7996 requests · 78 sessions
  67% of your usage came from subagent-heavy sessions
  66% of your usage was at >150k context
  11% of your usage came from sessions active for 8+ hours
  Top subagents: general-purpose 9%, fork 5%, claude 1%
  Top MCP servers: chrome-devtools 11%
"""


def cmd_usage(args: argparse.Namespace) -> None:
    if args.sample_passthrough:
        # Written through the same cache file fetch_usage() reads, so a concurrent web
        # request against api/usage_router.py (not just this CLI's own printing) picks it up
        # too -- the thing actually worth testing is the frontend's raw_text rendering,
        # which this CLI can't drive directly, but the shared cache file can feed.
        usage = Usage(raw_text=_SAMPLE_PASSTHROUGH_TEXT)
        _CACHE_PATH.write_text(usage.to_json())
        print(usage.raw_text)
        print(f"\n(written to {_CACHE_PATH} -- the web /usage page will show this until it's overwritten)")
        return

    try:
        usage = fetch_usage()
    except UsageFetchError as e:
        raise SystemExit(str(e))

    if usage.raw_text is not None:
        print(usage.raw_text)
        return

    assert usage.session_pct is not None and usage.session_resets_at is not None
    assert usage.week_pct is not None and usage.week_resets_at is not None
    print(_format_bar("Current session", usage.session_pct, usage.session_resets_at, SESSION_PERIOD))
    print(_format_bar("Current week (all models)", usage.week_pct, usage.week_resets_at, WEEK_PERIOD))
    print("\n`|`/`!` marks estimated pace -- where usage would be if spent evenly across the period.")


def add_usage_subparser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    """Registers `usage` onto an existing subparsers group -- called from stats.py's own
    add_subparser so this lives under `kb stats usage`, not as its own top-level noun."""
    parser = sub.add_parser("usage", help="Show Claude usage (mirrors the web /usage page)")
    parser.add_argument(
        "--sample-passthrough",
        action="store_true",
        help="Print sample no-usage-yet output instead of fetching real usage, to exercise "
        "the raw_text passthrough path (real API/frontend, not this CLI's own printing) "
        "without waiting for an actual empty usage window.",
    )
    parser.set_defaults(func=cmd_usage)
