"""Daily endpoints -- first concrete slice of the generic entity API, backing
the frontend's Dailies view. Read-scoped the same way `kb summary`/`daily
list` are: no context filter here (frontend browses everything for now);
add `context`/`contexts` query params later if a scoped view is needed."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_session
from models import Daily

router = APIRouter(prefix="/dailies")


class DailyOut(BaseModel):
    id: int
    description: str
    domain: str
    tier: str
    recurrence: str
    next_due_date: date
    location: Optional[str]
    remind_days_before: int
    is_active: bool
    notes: Optional[str]
    context_name: Optional[str]
    tag_name: Optional[str]
    is_due_now: bool
    is_overdue: bool


def _to_out(daily: Daily, session: Session) -> DailyOut:
    return DailyOut(
        id=daily.id,
        description=daily.description,
        domain=daily.domain,
        tier=daily.tier.value,
        recurrence=daily.recurrence,
        next_due_date=daily.next_due_date,
        location=daily.location,
        remind_days_before=daily.remind_days_before,
        is_active=daily.is_active,
        notes=daily.notes,
        context_name=daily.context.name if daily.context else None,
        tag_name=daily.tag.name if daily.tag else None,
        is_due_now=daily.is_due_now(session),
        is_overdue=daily.is_overdue(session),
    )


def _get_daily_or_404(session: Session, daily_id: int) -> Daily:
    daily = session.get(Daily, daily_id)
    if daily is None:
        raise HTTPException(status_code=404, detail="Daily not found")
    return daily


@router.get("", response_model=list[DailyOut])
async def list_dailies(
    due_only: bool = False,
    domain: Optional[str] = None,
    session: Session = Depends(get_session),
) -> list[DailyOut]:
    q = select(Daily).where(Daily.is_active.is_(True))
    if domain is not None:
        q = q.where(Daily.domain == domain)
    dailies = session.scalars(q).all()
    if due_only:
        dailies = [d for d in dailies if d.is_due_now(session)]
    return [_to_out(d, session) for d in dailies]


@router.get("/{daily_id}", response_model=DailyOut)
async def get_daily(daily_id: int, session: Session = Depends(get_session)) -> DailyOut:
    return _to_out(_get_daily_or_404(session, daily_id), session)


@router.post("/{daily_id}/complete", response_model=DailyOut)
async def complete_daily(daily_id: int, session: Session = Depends(get_session)) -> DailyOut:
    daily = _get_daily_or_404(session, daily_id)
    daily.complete(session)
    session.commit()
    session.refresh(daily)
    return _to_out(daily, session)


@router.post("/{daily_id}/catch-up", response_model=DailyOut)
async def catch_up_daily(daily_id: int, session: Session = Depends(get_session)) -> DailyOut:
    daily = _get_daily_or_404(session, daily_id)
    daily.catch_up(session)
    session.commit()
    session.refresh(daily)
    return _to_out(daily, session)
