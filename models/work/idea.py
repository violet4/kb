"""Idea, a someday/maybe project not yet committed to."""

from __future__ import annotations

import enum
from typing import Optional, Sequence

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base
from models.behaviors.embedding import HasEmbedding
from models.behaviors.placement import HasContextOrTag
from models.context import Context, Tag
from models.journal.tracking import HasJournal


class IdeaStatus(enum.Enum):
    ACTIVE = "active"  # sitting in someday/maybe, revisited only on deliberate review
    PROMOTED = "promoted"  # became a real Goal/Todo/Wishlist item (see Journal for which)
    DROPPED = "dropped"


class Idea(Base, HasContextOrTag, HasEmbedding, HasJournal):
    """GTD Someday/Maybe: a project idea you like but haven't committed to acting
    on, distinct from Todo (committed next-action work) and Wishlist (acquire/
    purchase, price-bearing). Deliberately has no defer_until, priority, or score --
    it never resurfaces on its own; you visit it on your own schedule (kb idea list),
    the same way GTD's Someday/Maybe list is only ever seen during a deliberate
    review, never pushed at you. Promotion to a real Goal/Todo/Wishlist is a manual
    relocation (create the new row by hand, record the transition via Journal,
    mark this PROMOTED) -- not a live foreign key, so promoted ideas don't leave a
    permanent cross-reference web behind them."""

    __tablename__ = "idea"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[IdeaStatus] = mapped_column(
        Enum(IdeaStatus, create_constraint=True, validate_strings=True), nullable=False, default=IdeaStatus.ACTIVE
    )
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional[Tag]] = relationship("Tag")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "description", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.description or ''}\n\n{self.notes or ''}"

    @classmethod
    def active(
        cls,
        session: Session,
        context: Optional[Context] = None,
        contexts: Optional[Sequence[Context]] = None,
    ) -> Sequence[Idea]:
        """`context` matches that single context exactly; `contexts` (e.g. from
        Context.self_and_descendants) matches any context in the given set, plus any
        Idea whose tag_id is carried by a Context in that set (see HasContextOrTag)."""
        q = select(cls).where(cls.status == IdeaStatus.ACTIVE, cls.deleted_at.is_(None))
        if context is not None:
            q = q.where(cls.context_id == context.id)
        if contexts is not None:
            matches = cls.matches_contexts(contexts)
            q = q.where(matches)
        return session.scalars(q).all()

    @classmethod
    def create(
        cls,
        session: Session,
        title: str,
        description: Optional[str] = None,
        context: Optional[Context] = None,
        tag: Optional[Tag] = None,
        notes: Optional[str] = None,
    ) -> Idea:
        idea = cls(
            title=title,
            description=description,
            context_id=context.id if context else None,
            tag_id=tag.id if tag else None,
            notes=notes,
        )
        idea.reembed()
        session.add(idea)
        session.flush()
        return idea

    def __repr__(self) -> str:
        return f"<Idea #{self.id} {self.title!r} [{self.status.value}]{self.age_marker()}>"
