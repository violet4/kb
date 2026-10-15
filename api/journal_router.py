"""Every record's history in one timeline, newest first -- backs the frontend's Journal view.
Per-record history stays on /entities/{type}/{id}/journal; this is the cross-record view."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.context_homes import contexts_by_tag
from api.deps import get_session
from api.record_hit import RecordHit, record_hit_fields
from api.serialize import utc_iso
from models.journal.journal import Journal
from models.links.entity_link import EntityLink

router = APIRouter(prefix="/journal")


class TimelineEntry(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: int
    record: Optional[RecordHit]  # None once the record is purged, or for a type with no table (SiNode)
    session_id: Optional[str]  # the harness's own session id, for /agents/{session_id}
    field: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    note: Optional[str]
    created_at_utc: str


class TimelinePage(BaseModel):
    entries: list[TimelineEntry]
    next_before: Optional[int]  # pass as `before` for the next, older page; None at the start of history


@router.get("", response_model=TimelinePage)
def timeline(
    before: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    include_reads: bool = False,
    session: Session = Depends(get_session),
) -> TimelinePage:
    entries = Journal.recent(session, limit, before_id=before, include_reads=include_reads)
    by_tag = contexts_by_tag(session)
    records: dict[tuple[str, int], Optional[RecordHit]] = {}
    for e in entries:
        key = (e.entity_type, e.entity_id)
        if key not in records:
            row = EntityLink.resolve(session, *key)
            records[key] = RecordHit(**record_hit_fields(session, row, by_tag)) if row is not None else None
    return TimelinePage(
        entries=[
            TimelineEntry(
                id=e.id,
                action=e.action.value,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                record=records[(e.entity_type, e.entity_id)],
                session_id=e.harness_session.harness_id if e.harness_session else None,
                field=e.field,
                old_value=e.shown_values()[0],
                new_value=e.shown_values()[1],
                note=e.note,
                created_at_utc=utc_iso(e.created_at) or "",
            )
            for e in entries
        ],
        next_before=entries[-1].id if len(entries) == limit else None,
    )
