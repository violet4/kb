"""Goal, a larger purpose or multi-step effort."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Optional, Sequence

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base
from models.behaviors.embedding import HasEmbedding
from models.behaviors.placement import HasContextOrTag
from models.context import Context, Tag
from models.journal.tracking import HasJournal
from models.links.auto_links import HasAutoLinks

if TYPE_CHECKING:
    from models.work.todo import Todo


class GoalStatus(enum.Enum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Goal(Base, HasContextOrTag, HasEmbedding, HasAutoLinks, HasJournal):
    __tablename__ = "goal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus, create_constraint=True, validate_strings=True), nullable=False, default=GoalStatus.ACTIVE
    )
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional[Tag]] = relationship("Tag")
    todos: Mapped[list[Todo]] = relationship("Todo", back_populates="goal")

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
    ) -> Sequence[Goal]:
        """`context` matches that single context exactly; `contexts` (e.g. from
        Context.self_and_descendants) matches any context in the given set, plus any
        Goal whose tag_id is carried by a Context in that set (see HasContextOrTag) --
        use the latter for a context-plus-sub-contexts filter."""
        q = select(cls).where(cls.status == GoalStatus.ACTIVE, cls.deleted_at.is_(None))
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
        notes: Optional[str] = None,
        tag: Optional[Tag] = None,
    ) -> Goal:
        goal = cls(title=title, description=description, context=context, tag=tag, notes=notes)
        goal.reembed()
        session.add(goal)
        session.flush()
        return goal

    def __repr__(self) -> str:
        size = len(self.title) + len(self.description or "") + len(self.notes or "")
        return f"<Goal #{self.id} {self.title!r} [{self.status.value}] {size}b{self.age_marker()}>"
