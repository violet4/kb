"""Timer, a countdown."""

from __future__ import annotations

import enum
from datetime import datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import Enum, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base, UtcDateTime, _now
from models.behaviors.placement import HasContextOrTag
from models.context import Context, Tag


class TimerStatus(enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Timer(Base, HasContextOrTag):
    """A DB-backed countdown, distinct from the stateless `timer` CLI -- persisted so a daemon
    process can track and alert on it independently of any running terminal. duration_seconds is
    the total length; ends_at is the single source of truth for when it fires, recomputed whenever
    the timer is (re)started so due-ness is a plain "now >= ends_at" comparison. repeat_count (None
    = run once, 0 = infinite, N = N total runs) mirrors the CLI's -r semantics; completed_runs
    tracks progress through it."""

    __tablename__ = "timer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    status: Mapped[TimerStatus] = mapped_column(
        Enum(TimerStatus, create_constraint=True, validate_strings=True), nullable=False, default=TimerStatus.ACTIVE
    )
    repeat_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional[Tag]] = relationship("Tag")

    @classmethod
    def active(
        cls,
        session: Session,
        context: Optional[Context] = None,
        contexts: Optional[Sequence[Context]] = None,
    ) -> Sequence[Timer]:
        """Same shape as Goal/Todo/Daily/Idea's .active() -- see Todo.active's docstring
        for why every context/tag-addressable entity matches this signature."""
        q = select(cls).where(cls.status == TimerStatus.ACTIVE, cls.deleted_at.is_(None))
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
        duration_seconds: int,
        label: Optional[str] = None,
        context: Optional[Context] = None,
        tag: Optional[Tag] = None,
        repeat_count: Optional[int] = None,
    ) -> Timer:
        timer = cls(
            label=label,
            duration_seconds=duration_seconds,
            ends_at=_now() + timedelta(seconds=duration_seconds),
            context_id=context.id if context else None,
            tag_id=tag.id if tag else None,
            repeat_count=repeat_count,
        )
        session.add(timer)
        session.flush()
        return timer

    def cancel(self) -> None:
        self.status = TimerStatus.CANCELLED

    def __repr__(self) -> str:
        label_str = f" {self.label!r}" if self.label else ""
        context_str = f" [{self.context.name}]" if self.context else ""
        tag_str = f" @{self.tag.name}" if self.tag else ""
        return (
            f"<Timer #{self.id}{label_str} [{self.status.value}] "
            f"ends_at={self.ends_at.strftime('%Y-%m-%d %H:%M:%S')}{context_str}{tag_str}>"
        )
