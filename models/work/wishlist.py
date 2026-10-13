"""Wishlist, something to acquire."""

from __future__ import annotations

import enum
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base
from models.context import Context
from models.journal.tracking import HasJournal


class WishlistStatus(enum.Enum):
    ACTIVE = "active"
    ACQUIRED = "acquired"
    DROPPED = "dropped"


class WishlistEffort(enum.Enum):
    GRAB = "grab"  # next time you're out
    RESEARCH = "research"  # needs investigation before buying
    PROJECT = "project"  # multi-step effort (e.g. server upgrade)


class Wishlist(Base, HasJournal):
    __tablename__ = "wishlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    price_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=50)  # 0–100
    urgency: Mapped[int] = mapped_column(Integer, nullable=False, default=50)  # 0–100
    effort: Mapped[WishlistEffort] = mapped_column(
        Enum(WishlistEffort, create_constraint=True, validate_strings=True), nullable=False, default=WishlistEffort.GRAB
    )
    clarity: Mapped[int] = mapped_column(Integer, nullable=False, default=50)  # 0–100: how well-defined the need is
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0–100: explicit deliberate rank
    status: Mapped[WishlistStatus] = mapped_column(
        Enum(WishlistStatus, create_constraint=True, validate_strings=True),
        nullable=False,
        default=WishlistStatus.ACTIVE,
    )
    context_id: Mapped[int] = mapped_column(Integer, ForeignKey("context.id"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # manually marked visible in kb summary

    context: Mapped[Context] = relationship("Context")

    @property
    def score(self) -> int:
        return self.importance * self.urgency * self.clarity // 10000

    @classmethod
    def active(
        cls,
        session: Session,
        effort: Optional[WishlistEffort] = None,
        contexts: Optional[Sequence[Context]] = None,
    ) -> Sequence[Wishlist]:
        q = select(cls).where(cls.status == WishlistStatus.ACTIVE, cls.deleted_at.is_(None))
        if contexts is not None:
            q = q.where(cls.context_id.in_([c.id for c in contexts]))
        if effort is not None:
            q = q.where(cls.effort == effort)
        return session.scalars(q).all()

    @classmethod
    def top(
        cls,
        session: Session,
        n: int = 10,
        pinned_only: bool = False,
        contexts: Optional[Sequence[Context]] = None,
    ) -> list[Wishlist]:
        """Active items: explicit priority first (nulls last), then score as tiebreaker."""
        items = cls.active(session, contexts=contexts)
        if pinned_only:
            items = [w for w in items if w.pinned]
        return sorted(items, key=lambda w: (w.priority is None, -(w.priority or 0), -w.score))[:n]

    def __repr__(self) -> str:
        price = ""
        if self.price_min is not None or self.price_max is not None:
            lo = f"${self.price_min}" if self.price_min is not None else ""
            hi = f"${self.price_max}" if self.price_max is not None else ""
            price = f" {lo}–{hi}" if lo and hi else f" {lo or hi}"
        priority_str = f" priority={self.priority}" if self.priority is not None else f" score={self.score}"
        pin = " pinned" if self.pinned else ""
        return f"<Wishlist #{self.id} {self.title!r}{price} [{self.context.name}] effort={self.effort.value}{priority_str}{pin}{self.age_marker()}>"
