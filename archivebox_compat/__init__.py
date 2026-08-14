"""Compat layer for talking to a live ArchiveBox instance ahead of the
real REST API stabilizing -- see get_client() in factory.py for the one
entry point, and kb Note 'ArchiveBox 0.8.x/0.9.x upgrade: rejected, no
stable release exists' for why this exists instead of just upgrading."""

from .client import ArchiveBoxClient
from .config import ArchiveBoxConfig, ArchiveBoxConfigError
from .factory import get_client
from .models import ArchiveMethodResult, Snapshot

__all__ = [
    "ArchiveBoxClient",
    "ArchiveBoxConfig",
    "ArchiveBoxConfigError",
    "ArchiveMethodResult",
    "Snapshot",
    "get_client",
]
