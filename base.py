"""Shared DeclarativeBase used by every model in this project, kb-native and game-specific alike."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, MetaData
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UtcDateTime(TypeDecorator[datetime]):
    """The one owner of kb's timestamp convention: every instant is stored as UTC. SQLite keeps
    no zone, so this converts a zone-aware value to UTC on write (a naive one is taken as UTC
    already) and marks every value read back as UTC -- callers always get an aware datetime,
    and its isoformat() always carries +00:00 across an API boundary."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect: Dialect) -> Optional[datetime]:
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value: Optional[datetime], dialect: Dialect) -> Optional[datetime]:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING_CONVENTION)

    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False, default=_now, onupdate=_now)
    # Soft-delete marker, on every model structurally (not a per-entity opt-in mixin) so a new
    # table can never be forgotten -- see kb si brittle-forgettable-defaults. NULL = not
    # deleted. `show`-ish commands intentionally do NOT filter on this (a deleted record is
    # still directly retrievable by id, with its deletion visible), only bulk list/search/
    # active-style queries do -- see kb_cli._util.not_deleted.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(UtcDateTime(), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

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
