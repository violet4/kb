"""Live harness-session listing and chat-transcript viewing, reusing
kb_cli.sessions.list_live_sessions/list_chat_messages (the same data `kb sessions list`
prints / a future `kb sessions show --chat` would) so the frontend and CLI can never drift
on what "listening"/"age"/"last message" mean or what counts as a chat message -- see those
functions' own docstrings."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_session
from harness import find_session_transcript_path
from kb_cli.sessions import list_chat_messages, list_live_sessions

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
    session.commit()  # persists list_live_sessions' stale-listener cleanup
    return [SessionOut(**info._asdict()) for info in infos]


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
