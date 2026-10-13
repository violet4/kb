"""InboxItem, a capture whose eventual home is not decided yet."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from models.base import Base, UtcDateTime, _now


class InboxItem(Base):
    """Raw, untriaged capture — the GTD inbox. Unlike everything else in kb, an InboxItem's
    eventual home isn't known at capture time: it might become a Todo, a Purchase, a LogEntry,
    a Note, or get discarded. Triage means deciding what it becomes, then marking triaged_at —
    triage is not a special mechanism, just create the right real record and mark this done."""

    __tablename__ = "inbox_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # capture channel, e.g. "email", "mobile", "quick-note"
    category: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # kind of content, e.g. "project-idea", "purchase"
    triaged_at: Mapped[Optional[datetime]] = mapped_column(UtcDateTime(), nullable=True)

    @classmethod
    def pending(cls, session: Session, category: Optional[str] = None) -> Sequence[InboxItem]:
        q = select(cls).where(cls.triaged_at.is_(None))
        if category is not None:
            q = q.where(cls.category == category)
        return session.scalars(q.order_by(cls.created_at)).all()

    @classmethod
    def create(
        cls, session: Session, body: str, source: Optional[str] = None, category: Optional[str] = None
    ) -> InboxItem:
        item = cls(body=body, source=source, category=category)
        session.add(item)
        session.flush()
        return item

    def triage(self) -> None:
        self.triaged_at = _now()

    def __repr__(self) -> str:
        state = "triaged" if self.triaged_at else "pending"
        tags = " ".join(f"[{t}]" for t in (self.category, self.source) if t)
        body = self.body if len(self.body) <= 60 else self.body[:60] + "…"
        return f"<InboxItem #{self.id} [{state}]{' ' + tags if tags else ''}: {body!r}>"
