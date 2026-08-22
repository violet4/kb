"""Usage endpoint -- shells out to `claude -p '/usage' --output-format json`
(no public API for this data, see kb Note on the /usage page) and parses the
plain-text session/week summary embedded in the JSON envelope's `result`
field into structured JSON for the frontend's ambient usage page."""

import json
import re
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/usage")

_SESSION_RE = re.compile(r"Current session:\s*(\d+)%\s*used\s*.*?resets\s*(.+)")
_WEEK_RE = re.compile(r"Current week \(all models\):\s*(\d+)%\s*used\s*.*?resets\s*(.+)")
_RESETS_RE = re.compile(r"^(.+?)\s*\(([^)]+)\)\s*$")


class UsageOut(BaseModel):
    session_pct: int
    session_resets: str
    session_resets_at: str
    week_pct: int
    week_resets: str
    week_resets_at: str


def _parse_resets_at(resets: str) -> str:
    """Parses e.g. "Aug 21, 6:19pm (America/Los_Angeles)" into an ISO 8601
    UTC timestamp. The claude CLI's output has no year, so the year is
    inferred as whichever of this-year/next-year keeps the reset in the
    future relative to now in that same timezone."""
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
    return parsed.astimezone(ZoneInfo("UTC")).isoformat()


@router.get("", response_model=UsageOut)
async def get_usage() -> UsageOut:
    try:
        result = subprocess.run(
            ["claude", "-p", "/usage", "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise HTTPException(status_code=502, detail=f"claude /usage failed: {e}")

    try:
        output = json.loads(result.stdout)["result"]
    except (json.JSONDecodeError, KeyError) as e:
        raise HTTPException(status_code=502, detail=f"could not parse claude /usage JSON envelope: {e}")

    session_match = _SESSION_RE.search(output)
    week_match = _WEEK_RE.search(output)
    if not session_match or not week_match:
        raise HTTPException(status_code=502, detail=f"could not parse claude /usage output: {output!r}")

    session_resets = session_match.group(2).strip()
    week_resets = week_match.group(2).strip()
    try:
        session_resets_at = _parse_resets_at(session_resets)
        week_resets_at = _parse_resets_at(week_resets)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=502, detail=f"could not parse reset timestamp: {e}")

    return UsageOut(
        session_pct=int(session_match.group(1)),
        session_resets=session_resets,
        session_resets_at=session_resets_at,
        week_pct=int(week_match.group(1)),
        week_resets=week_resets,
        week_resets_at=week_resets_at,
    )
