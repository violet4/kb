"""Live and past harness-session listing, plus chat-transcript viewing, reusing
kb_cli.sessions.list_live_sessions/list_history_sessions/list_chat_messages (the same data
`kb sessions list`/`kb sessions history` prints) so the frontend and CLI can never drift on
what "listening"/"age"/"last message" mean, what a past session's project/title is, or what
counts as a chat message -- see those functions' own docstrings."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.context_homes import contexts_by_tag
from api.deps import get_session
from api.record_hit import RecordHit, record_hit_fields
import harness_input
from harness import find_session_transcript_path
from kb_cli import si_files
from kb_cli.sessions import (
    interrupt_blocker,
    list_chat_messages,
    list_history_projects,
    list_history_sessions,
    list_live_sessions,
    prompt_blocker,
    rename_blocker,
)
from models.agents.harness_session import HarnessSession, HarnessSessionStatus
from models.journal.journal import Journal
from models.links.entity_link import EntityLink

router = APIRouter(prefix="/sessions")


class SessionOut(BaseModel):
    id: str
    is_self: bool
    status: str
    listening: str
    age_seconds: float
    last_message_seconds: float | None
    cwd: str
    title: str
    prompt_blocker: str | None
    interrupt_blocker: str | None
    rename_blocker: str | None


@router.get("", response_model=list[SessionOut])
async def get_live_sessions(session: Session = Depends(get_session)) -> list[SessionOut]:
    infos, _cleared_count = list_live_sessions(session)
    session.commit()  # persists list_live_sessions' stale-listener cleanup + TranscriptCache upserts
    return [SessionOut(**info._asdict()) for info in infos]


class SessionInputIn(BaseModel):
    text: str


@router.post("/{session_id}/input")
def post_session_input(
    session_id: str, body: SessionInputIn, session: Session = Depends(get_session)
) -> dict[str, bool]:
    """Submit `text` as a user prompt to a live session started with `kb claude`: as its next
    prompt when idle, or queued mid-turn (see prompt_blocker for when). 404 when the session
    is not live, 409 when prompt_blocker refuses or the wrapper is unreachable, 422 when the
    text is empty once control characters are removed."""
    row = _live_row(session, session_id)
    if blocker := prompt_blocker(row):
        raise HTTPException(status_code=409, detail=blocker)
    if not harness_input.clean(body.text):
        raise HTTPException(status_code=422, detail="Message is empty")
    try:
        harness_input.send(row.pid, body.text)
    except harness_input.InputError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # The session's prompt hook marks it busy too, but only once the prompt reaches it, so an
    # idle session would otherwise read idle for a moment after this send.
    row.status = HarnessSessionStatus.INFERRING
    session.commit()
    return {"ok": True}


@router.post("/{session_id}/interrupt")
def post_session_interrupt(session_id: str, session: Session = Depends(get_session)) -> dict[str, bool]:
    """Press Esc in a live `kb claude` session mid-turn, interrupting the turn or dismissing a
    permission dialog. Marks the session idle and clears awaiting_permission, since no hook
    reports an interrupted turn. 404 when the session is not live, 409 when
    interrupt_blocker refuses or the wrapper is unreachable."""
    row = _live_row(session, session_id)
    if blocker := interrupt_blocker(row):
        raise HTTPException(status_code=409, detail=blocker)
    try:
        harness_input.send_key(row.pid, "escape")
    except harness_input.InputError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    row.status = HarnessSessionStatus.IDLE
    row.awaiting_permission = False
    session.commit()
    return {"ok": True}


class SessionRenameIn(BaseModel):
    title: str


@router.post("/{session_id}/rename")
def post_session_rename(
    session_id: str, body: SessionRenameIn, session: Session = Depends(get_session)
) -> dict[str, bool]:
    """Send `/rename TITLE` to a live idle `kb claude` session. Leaves status alone: the
    command runs locally, so no turn starts and no hook would mark the session idle again. The
    new title reaches the listing through the transcript's custom-title event. 404 when the
    session is not live, 409 when rename_blocker refuses or the wrapper is unreachable, 422
    when the title is empty once control characters are removed."""
    row = _live_row(session, session_id)
    if blocker := rename_blocker(row):
        raise HTTPException(status_code=409, detail=blocker)
    # Every whitespace run becomes one space, so a newline cannot submit part of the title.
    title = " ".join(harness_input.clean(body.title).split())
    if not title:
        raise HTTPException(status_code=422, detail="Title is empty")
    try:
        harness_input.send(row.pid, f"/rename {title}")
    except harness_input.InputError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


def _live_row(session: Session, session_id: str) -> HarnessSession:
    row = HarnessSession.by_harness_id(session, session_id)
    if row is None or not row.is_alive():
        raise HTTPException(status_code=404, detail=f"No live session {session_id!r}")
    return row


class HistorySessionOut(BaseModel):
    id: str
    project: str
    title: str
    timestamp: str
    message_count: int


class HistoryProjectOut(BaseModel):
    project: str
    session_count: int


@router.get("/history/projects", response_model=list[HistoryProjectOut])
async def get_history_projects() -> list[HistoryProjectOut]:
    """Every project directory under ~/.claude/projects that has at least one past session --
    the frontend's project picker, most sessions first. Names are shown exactly as Claude
    Code writes them (dash-encoded absolute paths, not decoded back to a real path, since
    dashes-in-the-original-path vs. path-separator dashes can't be told apart). Reads
    directory names and *.jsonl counts only, no transcript parsing -- see
    list_history_projects's own docstring for why this must stay cheap."""
    return [HistoryProjectOut(**p._asdict()) for p in list_history_projects()]


@router.get("/history", response_model=list[HistorySessionOut])
async def get_history_sessions(
    project: Optional[str] = None, session: Session = Depends(get_session)
) -> list[HistorySessionOut]:
    """Past session transcripts, most recent first. `project` restricts to one project
    (a value from get_history_projects); omitted means every project. Reads through
    TranscriptCache (models/agents/transcript_cache.py), so a transcript whose mtime hasn't changed since it was
    last cached is a stat, not a full re-parse -- see TranscriptCache's own docstring."""
    sessions = list_history_sessions(session, project)
    session.commit()  # persists TranscriptCache upserts from list_history_sessions
    return [HistorySessionOut(**s._asdict()) for s in sessions]


class ChatBlockOut(BaseModel):
    kind: str
    text: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict[str, Any]] = None
    tool_output: Optional[str] = None
    is_error: bool = False
    tool_use_id: Optional[str] = None
    tags: dict[str, str] = {}


class ChatMessageOut(BaseModel):
    role: str
    timestamp: str
    blocks: list[ChatBlockOut]


class ChatPageOut(BaseModel):
    messages: list[ChatMessageOut]
    # Byte offset to pass as `offset` on the next request to get only newer messages.
    next_offset: int


@router.get("/{session_id}/chat", response_model=ChatPageOut)
async def get_session_chat(session_id: str, offset: int = Query(0, ge=0)) -> ChatPageOut:
    path = find_session_transcript_path(session_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"No transcript found for session {session_id!r}")
    messages, next_offset = list_chat_messages(path, offset)
    return ChatPageOut(
        messages=[
            ChatMessageOut(role=m.role, timestamp=m.timestamp, blocks=[ChatBlockOut(**b._asdict()) for b in m.blocks])
            for m in messages
        ],
        next_offset=next_offset,
    )


class TouchedRecordOut(RecordHit):
    changed: bool  # False when the session only read it
    last_at_utc: str


class SiNodeOut(BaseModel):
    id: int
    title: str


class SessionRefsOut(BaseModel):
    title: Optional[str]
    live: bool
    records: list[TouchedRecordOut]  # most recently touched first
    si_nodes: list[SiNodeOut]  # least recently read first, so a new read lands at the end


@router.get("/{session_id}/refs", response_model=SessionRefsOut)
async def get_session_refs(session_id: str, session: Session = Depends(get_session)) -> SessionRefsOut:
    """Every kb record one agent session has touched, from its Journal rows: what the Contexts
    page filters to while following the session. A deleted record is left out, since there
    is nothing left to show or link to; an si node is listed apart, having no context."""
    row = HarnessSession.by_harness_id(session, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No kb session {session_id!r}")
    by_tag = contexts_by_tag(session)
    records: list[TouchedRecordOut] = []
    si_nodes: list[SiNodeOut] = []
    for touched in Journal.touched_by(session, row.id):
        if touched.entity_type == "SiNode":
            node = si_files.resolve(str(touched.entity_id))
            if node is not None:
                si_nodes.append(SiNodeOut(id=touched.entity_id, title=node.title))
            continue
        item = EntityLink.resolve(session, touched.entity_type, touched.entity_id)
        if item is None or getattr(item, "deleted_at", None) is not None:
            continue
        records.append(
            TouchedRecordOut(
                **record_hit_fields(session, item, by_tag),
                changed=touched.changed,
                last_at_utc=touched.last_at.isoformat(),
            )
        )
    si_nodes.reverse()
    return SessionRefsOut(title=row.title, live=row.ended_at is None, records=records, si_nodes=si_nodes)
