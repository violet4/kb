"""Settings, the single-row table of standalone config values."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from models.base import Base


class Settings(Base):
    """Single-row table (id=1) for small standalone config values that don't belong on any
    other model. Start here before adding a dedicated settings table for a new value."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_boundary_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notifications_muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notifications_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    archivebox_host: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hard_delete_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    @classmethod
    def get(cls, session: Session) -> Settings:
        row = session.scalars(select(cls).filter_by(id=1)).one_or_none()
        if row is None:
            row = cls(id=1)
            session.add(row)
            session.flush()
        return row

    def resolved_timezone(self) -> ZoneInfo:
        """The IANA zone to use: an explicit override if set, else auto-detected from
        /etc/localtime (Linux's standard symlink to the system's zoneinfo file)."""
        if self.timezone:
            return ZoneInfo(self.timezone)
        localtime = Path("/etc/localtime")
        if localtime.is_symlink():
            target = str(localtime.resolve())
            marker = "zoneinfo/"
            if marker in target:
                return ZoneInfo(target.split(marker, 1)[1])
        return ZoneInfo("UTC")

    def __repr__(self) -> str:
        return f"<Settings day_boundary_hour={self.day_boundary_hour}>"
