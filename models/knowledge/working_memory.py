"""WorkingMemory, a topic's current working notes."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base
from models.context import Context


class WorkingMemory(Base):
    __tablename__ = "working_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    domain: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # e.g. "sqlalchemy", "arch-linux"
    body: Mapped[str] = mapped_column(Text, nullable=False)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")

    @classmethod
    def get(cls, session: Session, topic: str) -> Optional[WorkingMemory]:
        return session.scalars(select(cls).filter_by(topic=topic)).one_or_none()

    @classmethod
    def search(cls, session: Session, query: str) -> list[WorkingMemory]:
        q = query.lower()
        return [
            m
            for m in session.scalars(select(cls)).all()
            if q in m.topic.lower() or (m.domain and q in m.domain.lower()) or q in m.body.lower()
        ]

    @classmethod
    def get_or_create(cls, session: Session, topic: str, domain: Optional[str] = None, body: str = "") -> WorkingMemory:
        obj = cls.get(session, topic)
        if obj is None:
            obj = cls(topic=topic, domain=domain, body=body)
            session.add(obj)
            session.flush()
        return obj

    def __repr__(self) -> str:
        domain_str = f" [{self.domain}]" if self.domain else ""
        return f"<WorkingMemory {self.topic!r}{domain_str}{self.age_marker()}>"
