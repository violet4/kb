"""Vendor, somewhere Items are bought, and VendorItem, one Item at one Vendor."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.behaviors.embedding import HasEmbedding
from models.commerce.item import Item

# Vendor / VendorItem / Purchase — price/quantity history for anything
# transactable, real or in-game. A grocery store and an in-game shop NPC
# are both "somewhere you buy Items from"; domain distinguishes them.


class Vendor(Base, HasEmbedding):
    __tablename__ = "vendor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)  # "irl", "pg", ...
    kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # e.g. "grocery", "npc", "player_shop"
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"name", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.name}\n\n{self.notes}" if self.notes else self.name

    def __repr__(self) -> str:
        return f"<Vendor {self.name!r} [{self.domain}]{self.age_marker()}>"


class VendorItem(Base):
    """A vendor's own code for an Item — may differ from Item.upc (store-internal SKU vs.
    universal barcode), and differs vendor to vendor for the same Item."""

    __tablename__ = "vendor_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(Integer, ForeignKey("vendor.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("item.id"), nullable=False)
    vendor_sku: Mapped[str] = mapped_column(String, nullable=False)

    vendor: Mapped[Vendor] = relationship("Vendor")
    item: Mapped[Item] = relationship("Item")

    __table_args__ = (UniqueConstraint("vendor_id", "vendor_sku"),)

    def __repr__(self) -> str:
        return f"<VendorItem {self.vendor.name if self.vendor else '?'}:{self.vendor_sku} -> {self.item.name if self.item else '?'}>"
