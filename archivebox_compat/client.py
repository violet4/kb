"""ArchiveBoxClient is the one interface both backends implement -- see
scrape_backend.py (talks to a pinned pre-API instance via bs4 + Django admin
login) and rest_backend.py (talks to the real REST API once >=0.8 stabilizes).
A caller (kb_cli/archivebox.py) programs against this protocol only, never
against a backend class directly, so switching backends is a factory-level
change -- see factory.py's get_client() and kb Note archivebox-bs4-compat-layer
for why a live instance isn't in use yet."""

from __future__ import annotations

import builtins
from typing import Optional, Protocol

from .models import ArchiveMethodResult, Snapshot


class ArchiveBoxClient(Protocol):
    def add(self, url: str, *, tags: Optional[builtins.list[str]] = None, depth: int = 0) -> Snapshot: ...

    def list(
        self,
        *,
        search: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 200,
    ) -> builtins.list[Snapshot]: ...

    def get(self, snapshot_id: str) -> Optional[Snapshot]: ...

    def method_results(self, snapshot_id: str) -> builtins.list[ArchiveMethodResult]: ...

    def pull(self, snapshot_id: str) -> None: ...
