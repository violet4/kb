"""Connection config for the live ArchiveBox instance -- a plain dataclass, so a caller can
construct it however fits its own credential-sourcing story; this module doesn't dictate one.
kb (kb_cli/archivebox.py) owns auth end-to-end and builds ArchiveBoxConfig directly from
Settings.archivebox_host + kb_cli.secrets.get_credential(), never through from_env() below --
credentials live in the OS keyring, not environment variables, per kb Instruction #27
(security: don't cache credentials as a plain env var any process can read).

from_env() remains for non-kb callers (tests, standalone scripts) that don't have kb's keyring
wrapper available:

    ARCHIVEBOX_BASE_URL   e.g. https://archivebox.internal (no trailing slash)
    ARCHIVEBOX_USERNAME   Django admin username (ScrapeBackend only)
    ARCHIVEBOX_PASSWORD   Django admin password (ScrapeBackend only)
    ARCHIVEBOX_API_TOKEN  Bearer token (RestBackend only, >=0.8)
"""

from __future__ import annotations

import os
import ssl
from dataclasses import dataclass

import httpx

# archivebox.internal (and other private-CA-signed internal hosts) are signed by
# violet.com's own CA, present in the system trust store but not in the bundled
# certifi store httpx uses by default -- verified 2026-08-11, httpx.get() with the
# default verify=True fails CERTIFICATE_VERIFY_FAILED against archivebox.internal,
# succeeds once pointed at the system store below.
_SYSTEM_CA_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"


def _ssl_context() -> ssl.SSLContext | bool:
    if os.path.exists(_SYSTEM_CA_BUNDLE):
        return ssl.create_default_context(cafile=_SYSTEM_CA_BUNDLE)
    return True


class ArchiveBoxConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArchiveBoxConfig:
    base_url: str
    username: str | None = None
    password: str | None = None
    api_token: str | None = None

    @classmethod
    def from_env(cls) -> "ArchiveBoxConfig":
        base_url = os.environ.get("ARCHIVEBOX_BASE_URL")
        if not base_url:
            raise ArchiveBoxConfigError("ARCHIVEBOX_BASE_URL is not set")
        return cls(
            base_url=base_url.rstrip("/"),
            username=os.environ.get("ARCHIVEBOX_USERNAME"),
            password=os.environ.get("ARCHIVEBOX_PASSWORD"),
            api_token=os.environ.get("ARCHIVEBOX_API_TOKEN"),
        )

    def new_http_client(self, *, timeout: float = 30.0, follow_redirects: bool = False) -> httpx.Client:
        """The one place an httpx.Client is constructed against base_url --
        always trusts the system CA store (see _ssl_context) so internal-CA-signed
        hosts like archivebox.internal verify correctly."""
        return httpx.Client(
            base_url=self.base_url, verify=_ssl_context(), timeout=timeout, follow_redirects=follow_redirects
        )
