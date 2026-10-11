"""Serialization helpers shared by the API routers."""

from datetime import datetime, timezone
from typing import Optional


def utc_iso(value: Optional[datetime]) -> Optional[str]:
    """SQLite hands back naive datetimes; every kb timestamp is written as UTC (base.py's
    _now()), so stamp the zone before serializing."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
