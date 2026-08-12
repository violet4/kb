"""ArchiveBoxClient backend for the real REST API (>=0.8, stable target 0.9.x --
alpha status upstream as of 2026-08-11, endpoint paths verified against
docs.archivebox.io/dev/apidocs and mintlify.wiki/archivebox/archivebox/api/snapshots,
NOT yet exercised against a live instance since no >=0.8 deployment exists --
see kb Note 'ArchiveBox 0.8.x/0.9.x upgrade: rejected, no stable release exists').

Auth: Bearer token in the Authorization header (config.api_token), the
documented "best balance of security and convenience" method. GET
/api/v1/core/snapshots is confirmed; the create-snapshot endpoint's exact path
and body schema were NOT found in public docs as of this writing -- ADD_PATH
below is a best guess (mirrors the CLI's own `archivebox add` flags: url,
tag, depth) and must be confirmed/corrected against that instance's own
/api/v1/docs (OpenAPI/Swagger UI) the first time this backend is actually
switched on -- don't trust this guess silently."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx

from .config import ArchiveBoxConfig, ArchiveBoxConfigError
from .models import Snapshot

LIST_PATH = "/api/v1/core/snapshots"
ADD_PATH = "/api/v1/cli/add"  # best-effort guess, unconfirmed -- see module docstring


def _snapshot_from_json(data: dict[str, Any]) -> Snapshot:
    created_at = None
    raw_created = data.get("created_at")
    if raw_created:
        try:
            created_at = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
        except ValueError:
            created_at = None
    return Snapshot(
        id=str(data.get("id", "")),
        url=data.get("url", ""),
        status=data.get("status", "unknown"),
        title=data.get("title"),
        created_at=created_at,
        tags=list(data.get("tags") or []),
        num_archiveresults=data.get("num_archiveresults"),
    )


class RestBackend:
    def __init__(self, config: ArchiveBoxConfig, *, client: Optional[httpx.Client] = None) -> None:
        if not config.api_token:
            raise ArchiveBoxConfigError("RestBackend requires ARCHIVEBOX_API_TOKEN")
        self._client = client or config.new_http_client()
        self._client.headers.update({"Authorization": f"Bearer {config.api_token}", "Accept": "application/json"})

    def add(self, url: str, *, tags: Optional[list[str]] = None, depth: int = 0) -> Snapshot:
        resp = self._client.post(ADD_PATH, json={"urls": [url], "tag": ",".join(tags or []), "depth": depth})
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items") if isinstance(data, dict) else None
        return _snapshot_from_json((items[0] if items else data))

    def list(
        self,
        *,
        search: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 200,
    ) -> list[Snapshot]:
        params: dict[str, Any] = {"limit": limit}
        if search:
            params["search"] = search
        if tag:
            params["tag"] = tag
        resp = self._client.get(LIST_PATH, params=params)
        resp.raise_for_status()
        data = resp.json()
        return [_snapshot_from_json(item) for item in data.get("items", [])]

    def get(self, snapshot_id: str) -> Optional[Snapshot]:
        resp = self._client.get(f"{LIST_PATH.replace('snapshots', 'snapshot')}/{snapshot_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return _snapshot_from_json(resp.json())
