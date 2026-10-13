"""Person, someone to keep in touch with."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import Enum, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from models.base import Base, UtcDateTime, _now


class PersonTier(enum.Enum):
    CLOSE = "close"
    ACQUAINTANCE = "acquaintance"
    PUBLIC_FIGURE = "public_figure"


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[PersonTier] = mapped_column(
        Enum(PersonTier, create_constraint=True, validate_strings=True), nullable=False, default=PersonTier.ACQUAINTANCE
    )
    closeness: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_contacted: Mapped[Optional[datetime]] = mapped_column(UtcDateTime(), nullable=True)
    reach_out_every_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @classmethod
    def get(cls, session: Session, name: str) -> Optional[Person]:
        return session.scalars(select(cls).filter_by(name=name)).one_or_none()

    @classmethod
    def get_or_create(cls, session: Session, name: str, tier: PersonTier = PersonTier.ACQUAINTANCE) -> Person:
        obj = cls.get(session, name)
        if obj is None:
            obj = cls(name=name, tier=tier)
            session.add(obj)
            session.flush()
        return obj

    @classmethod
    def in_my_life(cls, session: Session) -> Sequence[Person]:
        """People who are part of my immediate surrounding life (excludes public figures)."""
        return session.scalars(
            select(cls).where(cls.tier != PersonTier.PUBLIC_FIGURE).order_by(cls.closeness.desc())
        ).all()

    @classmethod
    def overdue_for_contact(cls, session: Session) -> list[Person]:
        """People I should have reached out to by now, ordered by most overdue."""
        now = _now()
        candidates = session.scalars(
            select(cls).where(cls.tier != PersonTier.PUBLIC_FIGURE).where(cls.reach_out_every_days.isnot(None))
        ).all()
        overdue: list[tuple[Person, Optional[int]]] = []
        for p in candidates:
            if p.last_contacted is None:
                overdue.append((p, None))
            else:
                days_since = (now - p.last_contacted).days
                assert p.reach_out_every_days is not None  # guaranteed by the isnot(None) filter above
                if days_since >= p.reach_out_every_days:
                    overdue.append((p, days_since))
        overdue.sort(key=lambda x: (x[1] is None, -(x[1] or 0)))
        return [p for p, _ in overdue]

    def __repr__(self) -> str:
        return f"<Person {self.name!r} [{self.tier.value}] closeness={self.closeness}{self.age_marker()}>"
