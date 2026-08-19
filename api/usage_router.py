"""Usage endpoint -- shells out to `claude -p '/usage' --output-format json`
(no public API for this data, see kb Note on the /usage page) and parses the
plain-text session/week summary embedded in the JSON envelope's `result`
field into structured JSON for the frontend's ambient usage page."""

import json
import re
import subprocess

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/usage")

_SESSION_RE = re.compile(r"Current session:\s*(\d+)%\s*used\s*.*?resets\s*(.+)")
_WEEK_RE = re.compile(r"Current week \(all models\):\s*(\d+)%\s*used\s*.*?resets\s*(.+)")


class UsageOut(BaseModel):
    session_pct: int
    session_resets: str
    week_pct: int
    week_resets: str


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

    return UsageOut(
        session_pct=int(session_match.group(1)),
        session_resets=session_match.group(2).strip(),
        week_pct=int(week_match.group(1)),
        week_resets=week_match.group(2).strip(),
    )
