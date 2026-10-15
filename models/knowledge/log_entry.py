"""LogEntry, a fact about the world at a point in time."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base, UtcDateTime, _now
from models.behaviors.embedding import HasEmbedding
from models.context import Context
from models.journal.tracking import HasJournal
from models.links.auto_links import HasAutoLinks


class LogEntry(Base, HasEmbedding, HasAutoLinks, HasJournal):
    """A timestamped observation — a fact or set of facts about a moment, not durable reference
    knowledge and not work with a status. Append-only; the point is to build a queryable history
    (health, events, commits referenced by free text) that reveals patterns over time. domain is
    a loose, unenforced label (e.g. "health", "cat", "work") — let structure emerge from actual
    use rather than pre-defining categories."""

    __tablename__ = "log_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False, default=_now)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    context_id: Mapped[int] = mapped_column(Integer, ForeignKey("context.id"), nullable=False)

    context: Mapped[Context] = relationship("Context")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"body"}

    def _embed_source_text(self) -> str:
        return self.body

    @classmethod
    def create(
        cls,
        session: Session,
        body: str,
        context: Context,
        domain: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
    ) -> LogEntry:
        entry = cls(
            body=body,
            domain=domain,
            context=context,
            occurred_at=occurred_at or _now(),
        )
        entry.reembed()
        session.add(entry)
        session.flush()
        return entry

    @classmethod
    def recent(
        cls,
        session: Session,
        domain: Optional[str] = None,
        context: Optional[Context] = None,
        limit: int = 20,
        since: Optional[datetime] = None,
    ) -> Sequence[LogEntry]:
        q = select(cls).where(cls.deleted_at.is_(None)).order_by(cls.occurred_at.desc(), cls.id.desc()).limit(limit)
        if domain is not None:
            q = q.where(cls.domain == domain)
        if context is not None:
            q = q.where(cls.context_id == context.id)
        if since is not None:
            q = q.where(cls.occurred_at >= since)
        return session.scalars(q).all()

    def __repr__(self) -> str:
        when = self.occurred_at.strftime("%Y-%m-%d")
        body = self.body if len(self.body) <= 60 else self.body[:60] + "…"
        return f"<LogEntry #{self.id} [{when}]{' ' + self.domain if self.domain else ''}: {body!r}>"
