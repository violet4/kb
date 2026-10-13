"""TranscriptCache, parsed metadata of a session transcript."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from models.base import Base, UtcDateTime, _now


class TranscriptCache(Base):
    """Memoizes the per-line-scan result of parsing one Claude Code session transcript
    (~/.claude/projects/*/*.jsonl) -- title, message_count -- keyed by session id (the
    transcript's filename stem, already globally unique per HarnessSession's own docstring).
    Every caller that needs a transcript's derived fields (kb_cli.sessions.list_history_sessions
    for `kb sessions history`/the frontend's past-sessions list, refresh_agent_title for the
    live Agents view) should read through get_or_refresh() rather than opening the file directly,
    so a transcript already scanned once this session/day is never re-parsed for the same
    unchanged content -- these files are append-only during a live session and immutable once
    it ends, but both the live Agents view (polled continuously) and the history view (opened
    repeatedly while browsing) were re-scanning the same bytes on every single read before
    this existed, confirmed live 2026-09-01 as measurably slow on a 20MB/5000-line transcript.

    file_mtime is the dirty check: read via one cheap os.stat() (no file open) on every
    lookup and compared against the stored value -- a real Claude Code transcript is
    append-only while its session is live and untouched once the session ends, so mtime
    strictly increases with new content and never regresses without the file being rewritten
    out from under us (not a real case for these files), making it a sound proxy for content
    change; not a content hash, since a hash still requires reading the whole file, defeating
    the point of caching in the first place. mtime is stored as a DateTime for consistency
    with every other timestamp column in this file, not a Float epoch value which nothing
    else here uses."""

    __tablename__ = "transcript_cache"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    project: Mapped[str] = mapped_column(String, nullable=False)
    file_mtime: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False, default=_now)

    @classmethod
    def get_or_refresh(cls, session: Session, path: Path) -> Optional["TranscriptCache"]:
        """Returns the cached row for `path`'s session id, re-parsing and upserting it first
        if the row is missing or its stored file_mtime doesn't match the file's current
        mtime. None if the transcript is empty/unreadable (nothing worth caching) --
        matches kb_cli.sessions._session_info's own None-on-empty contract, which this
        method wraps rather than replaces (parsing logic has exactly one owner, there;
        imported locally to avoid a models.py <-> kb_cli.sessions import cycle)."""
        from kb_cli.sessions import _session_info

        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        row = session.get(cls, path.stem)
        if row is not None and row.file_mtime == mtime:
            return row

        info = _session_info(path)
        if info is None:
            if row is not None:
                session.delete(row)
            return None

        if row is None:
            row = cls(session_id=path.stem, project=path.parent.name)
            session.add(row)
        row.project = path.parent.name
        row.file_mtime = mtime
        row.title = info["title"]
        row.message_count = info["message_count"]
        row.updated_at = _now()
        session.flush()
        return row

    def __repr__(self) -> str:
        return f"<TranscriptCache {self.session_id[:8]} {self.message_count} msgs>"
