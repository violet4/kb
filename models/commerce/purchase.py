"""Purchase, one price and quantity observation of a VendorItem."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, UtcDateTime, _now
from models.behaviors.embedding import HasEmbedding
from models.commerce.vendor import VendorItem


class Purchase(Base, HasEmbedding):
    __tablename__ = "purchase"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("vendor_item.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=1)
    unit_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    total_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    purchased_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False, default=_now)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    vendor_item: Mapped[VendorItem] = relationship("VendorItem")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"notes"}

    def _embed_source_text(self) -> str:
        item_name = self.vendor_item.item.name if self.vendor_item and self.vendor_item.item else ""
        return f"{item_name}\n\n{self.notes}" if self.notes else item_name

    def __repr__(self) -> str:
        return (
            f"<Purchase {self.quantity}x {self.vendor_item.item.name if self.vendor_item else '?'} @ {self.unit_price}>"
        )
