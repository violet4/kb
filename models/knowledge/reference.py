"""Reference, a pointer to an external resource."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base
from models.context import Context


class Reference(Base):
    __tablename__ = "reference"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # comma-separated
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")

    @classmethod
    def search(cls, session: Session, query: str) -> list[Reference]:
        q = query.lower()
        return [
            r
            for r in session.scalars(select(cls)).all()
            if q in r.title.lower() or (r.tags and q in r.tags.lower()) or (r.notes and q in r.notes.lower())
        ]

    @classmethod
    def create(
        cls,
        session: Session,
        title: str,
        url: Optional[str] = None,
        tags: Optional[str] = None,
        context: Optional[Context] = None,
        notes: Optional[str] = None,
    ) -> Reference:
        ref = cls(title=title, url=url, tags=tags, context_id=context.id if context else None, notes=notes)
        session.add(ref)
        session.flush()
        return ref

    def __repr__(self) -> str:
        return f"<Reference {self.title!r}{self.age_marker()}>"
