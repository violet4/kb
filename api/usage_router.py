"""Usage endpoints -- thin wrapper around kb_cli.usage's shared fetch/parse logic
(see that module for `claude -p /usage` shelling-out details), returned as JSON
for the frontend's ambient usage page."""

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from kb_cli.usage import UsageFetchError, fetch_usage
from models import SessionFactory, UsageSample

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


class UsageSampleOut(BaseModel):
    sampled_at: str
    session_pct: int
    session_resets_at: str
    week_pct: int
    week_resets_at: str


def _fetch_history_sync(since: datetime) -> list[UsageSampleOut]:
    session = SessionFactory()
    try:
        samples = session.scalars(
            select(UsageSample).where(UsageSample.sampled_at >= since).order_by(UsageSample.sampled_at)
        ).all()
        return [
            UsageSampleOut(
                sampled_at=s.sampled_at.replace(tzinfo=timezone.utc).isoformat(),
                session_pct=s.session_pct,
                session_resets_at=s.session_resets_at.replace(tzinfo=timezone.utc).isoformat(),
                week_pct=s.week_pct,
                week_resets_at=s.week_resets_at.replace(tzinfo=timezone.utc).isoformat(),
            )
            for s in samples
        ]
    finally:
        session.close()


@router.get("/history", response_model=list[UsageSampleOut])
async def get_usage_history(hours: float = 5.0) -> list[UsageSampleOut]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    return await asyncio.to_thread(_fetch_history_sync, since)
