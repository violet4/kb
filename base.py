"""Shared DeclarativeBase used by every model in this project, kb-native and game-specific alike."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING_CONVENTION)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    def age_marker(self) -> str:
        """Renders as " (Nd old)"/" (Nw old)" from updated_at, or "" if updated within the last day --
        every __repr__ appends this, so age is visible in `search`/`list` output (a plain
        substring/id scan, not just `show`), not just the full created_at/updated_at lines
        `show` commands print via kb_cli._util.print_timestamps. This is what lets a kb record's
        age be weighed at the point a claim is actually read/relayed (temporal-record-skepticism,
        kb Instruction #81), rather than requiring a separate deliberate date lookup."""
        delta = _now() - self.updated_at.replace(tzinfo=timezone.utc)
        days = delta.days
        if days < 1:
            return ""
        if days < 14:
            return f" ({days}d old)"
        return f" ({days // 7}w old)"
