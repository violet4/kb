"""get_client() is the one place callers ask for an ArchiveBoxClient -- never
construct ScrapeBackend/RestBackend directly, so the scrape-vs-rest choice
stays a single switch point instead of scattered version checks.

Detection: GET {base_url}/api/v1/core/snapshots -- present and returning JSON
(not a 404/redirect-to-login-page) means a REST-API-capable instance (>=0.8)
is live, so RestBackend is used. Anything else (404, HTML response, connection
refused) falls back to ScrapeBackend, matching the pinned 0.7.4 instance this
compat layer was built for. Pass backend="scrape"/"rest" to force one
explicitly instead of probing (e.g. for tests, or once the real upgrade to
>=0.8 happens and probing is no longer needed)."""

from __future__ import annotations

from typing import Literal, Optional

import httpx

from .client import ArchiveBoxClient
from .config import ArchiveBoxConfig
from .rest_backend import LIST_PATH as REST_PROBE_PATH
from .rest_backend import RestBackend
from .scrape_backend import ScrapeBackend


def _probe_rest_api(config: ArchiveBoxConfig) -> bool:
    try:
        with config.new_http_client(timeout=5.0) as client:
            resp = client.get(REST_PROBE_PATH)
    except httpx.HTTPError:
        return False
    if resp.status_code != 200:
        return False
    return "application/json" in resp.headers.get("content-type", "")


def get_client(
    config: Optional[ArchiveBoxConfig] = None,
    *,
    backend: Optional[Literal["scrape", "rest"]] = None,
) -> ArchiveBoxClient:
    config = config or ArchiveBoxConfig.from_env()
    if backend is None:
        backend = "rest" if _probe_rest_api(config) else "scrape"
    if backend == "rest":
        return RestBackend(config)
    return ScrapeBackend(config)
