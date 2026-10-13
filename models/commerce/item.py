"""Item, anything that can be bought, and its subtypes."""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base
from models.behaviors.embedding import HasEmbedding
from models.columns import HasWeight
from models.context import Context


class Item(Base, HasEmbedding):
    """JTI base for items. Each subtype's side table joins 1:1 via id, `game` is the polymorphic
    discriminator, and a subtype composes whichever mixins.py traits it needs."""

    __tablename__ = "item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    upc: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")

    __mapper_args__ = {"polymorphic_on": "game", "polymorphic_identity": "item"}

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"name", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.name}\n\n{self.notes}" if self.notes else self.name

    @classmethod
    def by_game(cls, session: Session, game: str) -> Sequence[Item]:
        return session.scalars(select(cls).filter_by(game=game)).all()

    def __repr__(self) -> str:
        return f"<Item #{self.id} {self.name!r} [{self.game}]{self.age_marker()}>"


class IrlItem(Item, HasWeight):
    """Real-world items — groceries, household goods, etc. Tracked the same way as game
    items (Vendor/VendorItem/Purchase apply equally): we can never see a store's whole
    price history at once, only snippets over time, same as an in-game player market."""

    __tablename__ = "irl_item"

    id: Mapped[int] = mapped_column(Integer, ForeignKey("item.id"), primary_key=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # free text, e.g. "5.5oz can"

    __mapper_args__ = {"polymorphic_identity": "irl"}
