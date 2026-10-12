"""Serialization helpers shared by the API routers."""

from datetime import datetime
from typing import Optional


def utc_iso(value: Optional[datetime]) -> Optional[str]:
    """An optional UTC instant as ISO 8601 with its +00:00 offset (UtcDateTime columns are
    always read back zone-aware, so the offset is never missing)."""
    return value.isoformat() if value is not None else None
