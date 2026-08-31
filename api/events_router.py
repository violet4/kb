"""Event endpoints, backing the frontend's Events (calendar) view -- same shape as
dailies_router.py, computed fields (next_occurrence) added the same way is_due_now/
is_overdue are added to DailyOut. Unscoped by default, matching dailies_router.py's
"frontend browses everything for now" convention."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_session
from models import Event

router = APIRouter(prefix="/events")


class EventOut(BaseModel):
    id: int
    title: str
    starts_at: datetime
    is_all_day: bool
    recurrence: Optional[str]
    notes: Optional[str]
    context_name: Optional[str]
    tag_name: Optional[str]
    next_occurrence: Optional[datetime]


def _to_out(event: Event) -> EventOut:
    return EventOut(
        id=event.id,
        title=event.title,
        starts_at=event.starts_at,
        is_all_day=event.is_all_day,
        recurrence=event.recurrence,
        notes=event.notes,
        context_name=event.context.name if event.context else None,
        tag_name=event.tag.name if event.tag else None,
        next_occurrence=event.next_occurrence(),
    )


def _get_event_or_404(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("", response_model=list[EventOut])
async def list_events(upcoming_only: bool = True, session: Session = Depends(get_session)) -> list[EventOut]:
    events = session.scalars(select(Event)).all()
    out = [_to_out(e) for e in events]
    if upcoming_only:
        out = [e for e in out if e.next_occurrence is not None]
    out.sort(key=lambda e: e.next_occurrence or e.starts_at)
    return out


class EventCreateIn(BaseModel):
    title: str
    starts_at: datetime
    is_all_day: bool = False
    recurrence: Optional[str] = None
    notes: Optional[str] = None


@router.post("", response_model=EventOut)
async def create_event(body: EventCreateIn, session: Session = Depends(get_session)) -> EventOut:
    event = Event.create(
        session,
        body.title,
        body.starts_at,
        is_all_day=body.is_all_day,
        recurrence=body.recurrence,
        notes=body.notes,
    )
    session.commit()
    return _to_out(event)


class EventOccurrenceOut(BaseModel):
    """One (Event, occurrence instant) pair -- a recurring Event contributes one of
    these per occurrence landing inside the queried range, so a calendar grid gets a
    flat list of cells to place rather than expanding recurrence client-side."""

    event: EventOut
    occurs_at: datetime


@router.get("/range", response_model=list[EventOccurrenceOut])
async def list_events_in_range(
    start: datetime, end: datetime, session: Session = Depends(get_session)
) -> list[EventOccurrenceOut]:
    """Every Event occurrence landing in [start, end) -- backs the week/month calendar
    grid views, which need every occurrence in view, not just each Event's single next
    one (list_events/EventOut.next_occurrence). Registered before /{event_id} so "range"
    isn't swallowed as an event_id path param."""
    events = session.scalars(select(Event)).all()
    out = []
    for event in events:
        event_out = _to_out(event)
        for occ in event.occurrences_between(start, end):
            out.append(EventOccurrenceOut(event=event_out, occurs_at=occ))
    out.sort(key=lambda o: o.occurs_at)
    return out


@router.get("/{event_id}", response_model=EventOut)
async def get_event(event_id: int, session: Session = Depends(get_session)) -> EventOut:
    return _to_out(_get_event_or_404(session, event_id))
