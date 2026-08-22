"""Usage endpoint -- thin wrapper around kb_cli.usage's shared fetch/parse logic
(see that module for `claude -p /usage` shelling-out details), returned as JSON
for the frontend's ambient usage page."""

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kb_cli.usage import UsageFetchError, fetch_usage

router = APIRouter(prefix="/usage")


class UsageOut(BaseModel):
    session_pct: int
    session_resets: str
    session_resets_at: str
    week_pct: int
    week_resets: str
    week_resets_at: str


@router.get("", response_model=UsageOut)
async def get_usage() -> UsageOut:
    try:
        # fetch_usage() shells out and blocks for the claude CLI's response (multiple
        # seconds) -- run it in a thread so it doesn't stall the asyncio event loop, which
        # would otherwise hang every other concurrent request behind this one.
        usage = await asyncio.to_thread(fetch_usage)
    except UsageFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return UsageOut(
        session_pct=usage.session_pct,
        session_resets=usage.session_resets,
        session_resets_at=usage.session_resets_at.isoformat(),
        week_pct=usage.week_pct,
        week_resets=usage.week_resets,
        week_resets_at=usage.week_resets_at.isoformat(),
    )
