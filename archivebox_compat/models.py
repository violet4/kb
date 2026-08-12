"""Snapshot shape shared by every backend -- mirrors the documented ArchiveBox
REST API response schema (GET /api/v1/core/snapshots, verified 2026-08-11 against
docs.archivebox.io/dev/apidocs and mintlify.wiki/archivebox/archivebox/api/snapshots),
not any one backend's native format. A backend's job is only to produce/consume this
shape -- see client.py's ArchiveBoxClient for the protocol both backends implement."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Snapshot:
    id: str
    url: str
    status: str  # "queued" | "started" | "succeeded" | "failed" | "sealed" | "unknown"
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    num_archiveresults: Optional[int] = None
