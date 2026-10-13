"""LogEntry capture from the browser: the most recent entries, and one-shot creation
-- backs the frontend's Log view, a quick "record a fact about the world" surface."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_session
from api.serialize import utc_iso
from models.context import Context
from models.knowledge.log_entry import LogEntry

router = APIRouter(prefix="/log")


class ContextRef(BaseModel):
    id: int
    name: str


class LogItem(BaseModel):
    id: int
    body: str
    domain: Optional[str]
    context: ContextRef
    occurred_at_utc: Optional[str]
    created_at_utc: Optional[str]


class LogCreate(BaseModel):
    body: str = Field(min_length=1)
    context_id: int


def _item(entry: LogEntry) -> LogItem:
    return LogItem(
        id=entry.id,
        body=entry.body,
        domain=entry.domain,
        context=ContextRef(id=entry.context.id, name=entry.context.name),
        occurred_at_utc=utc_iso(entry.occurred_at),
        created_at_utc=utc_iso(entry.created_at),
    )


@router.get("/recent", response_model=list[LogItem])
def recent(limit: int = Query(50, ge=1, le=500), session: Session = Depends(get_session)) -> list[LogItem]:
    return [_item(e) for e in LogEntry.recent(session, limit=limit)]


@router.post("", response_model=LogItem)
def create(payload: LogCreate, session: Session = Depends(get_session)) -> LogItem:
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="body is empty")
    context = session.get(Context, payload.context_id)
    if context is None or context.deleted_at is not None:
        raise HTTPException(status_code=400, detail=f"Context:{payload.context_id} not found")
    entry = LogEntry.create(session, body, context=context)
    session.commit()
    return _item(entry)
