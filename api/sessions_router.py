"""Live and past harness-session listing, plus chat-transcript viewing, reusing
kb_cli.sessions.list_live_sessions/list_history_sessions/list_chat_messages (the same data
`kb sessions list`/`kb sessions history` prints) so the frontend and CLI can never drift on
what "listening"/"age"/"last message" mean, what a past session's project/title is, or what
counts as a chat message -- see those functions' own docstrings."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_session
from harness import find_session_transcript_path
from kb_cli.sessions import list_chat_messages, list_history_projects, list_history_sessions, list_live_sessions

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


@router.get("", response_model=list[SessionOut])
async def get_live_sessions(session: Session = Depends(get_session)) -> list[SessionOut]:
    infos, _cleared_count = list_live_sessions(session)
    session.commit()  # persists list_live_sessions' stale-listener cleanup + TranscriptCache upserts
    return [SessionOut(**info._asdict()) for info in infos]


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
    TranscriptCache (models.py), so a transcript whose mtime hasn't changed since it was
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
    tags: dict[str, str] = {}


class ChatMessageOut(BaseModel):
    role: str
    timestamp: str
    blocks: list[ChatBlockOut]


@router.get("/{session_id}/chat", response_model=list[ChatMessageOut])
async def get_session_chat(session_id: str) -> list[ChatMessageOut]:
    path = find_session_transcript_path(session_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"No transcript found for session {session_id!r}")
    messages = list_chat_messages(path)
    return [
        ChatMessageOut(role=m.role, timestamp=m.timestamp, blocks=[ChatBlockOut(**b._asdict()) for b in m.blocks])
        for m in messages
    ]
