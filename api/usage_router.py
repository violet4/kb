"""Usage endpoint -- thin wrapper around kb_cli.usage's shared fetch/parse logic
(see that module for `claude -p /usage` shelling-out details), returned as JSON
for the frontend's ambient usage page."""

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kb_cli.usage import UsageFetchError, fetch_usage

router = APIRouter(prefix="/usage")


class UsageOut(BaseModel):
    session_pct: int | None = None
    session_resets: str | None = None
    session_resets_at: str | None = None
    week_pct: int | None = None
    week_resets: str | None = None
    week_resets_at: str | None = None
    raw_text: str | None = None


@router.get("", response_model=UsageOut)
async def get_usage() -> UsageOut:
    try:
        # fetch_usage() shells out and blocks for the claude CLI's response (multiple
        # seconds) -- run it in a thread so it doesn't stall the asyncio event loop, which
        # would otherwise hang every other concurrent request behind this one.
        usage = await asyncio.to_thread(fetch_usage)
    except UsageFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if usage.raw_text is not None:
        return UsageOut(raw_text=usage.raw_text)

    assert usage.session_pct is not None and usage.session_resets_at is not None
    assert usage.week_pct is not None and usage.week_resets_at is not None
    return UsageOut(
        session_pct=usage.session_pct,
        session_resets=usage.session_resets,
        session_resets_at=usage.session_resets_at.isoformat(),
        week_pct=usage.week_pct,
        week_resets=usage.week_resets,
        week_resets_at=usage.week_resets_at.isoformat(),
    )
