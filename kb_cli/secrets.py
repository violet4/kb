"""Thin wrapper over the OS keyring (Secret Service/KWallet) for credentials kb needs to hand
to external services -- kb owns auth for every integration (e.g. ArchiveBox), never delegates
credential sourcing to that integration's own library, per kb Instruction #27 (security).
Reusable across services: pass a distinct `service` name per integration (e.g.
"kb-archivebox") rather than adding a new module per credential.

keyring.get_password() has no built-in timeout -- if it's ever called somewhere with no D-Bus
session/display (SSH, cron, a systemd service), the Secret Service unlock prompt has nowhere to
render and the call can hang forever instead of failing. get_credential() below always runs it
in a worker thread with an explicit timeout so a headless invocation fails fast with a clear
error instead of hanging."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Optional

import keyring

_UNLOCK_TIMEOUT_SECONDS = 10.0
_USERNAME_KEY = "username"
_PASSWORD_KEY = "password"


class CredentialUnavailableError(RuntimeError):
    """Raised when the keyring can't be reached (locked with no prompter available, or
    genuinely not configured) -- callers should report this clearly, not retry silently."""


def get_credential(service: str) -> Optional[tuple[str, str]]:
    """(username, password) stored for `service`, or None if never configured. Raises
    CredentialUnavailableError if the keyring itself can't be reached in time (e.g. no desktop
    session to show an unlock prompt)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        username_future = pool.submit(keyring.get_password, service, _USERNAME_KEY)
        try:
            username = username_future.result(timeout=_UNLOCK_TIMEOUT_SECONDS)
        except FutureTimeoutError as exc:
            raise CredentialUnavailableError(
                f"keyring did not respond within {_UNLOCK_TIMEOUT_SECONDS:.0f}s for service "
                f"{service!r} -- if this is running headless (no desktop session), the OS "
                "keyring can't show its unlock prompt; run this interactively instead"
            ) from exc
        if username is None:
            return None
        password_future = pool.submit(keyring.get_password, service, username)
        try:
            password = password_future.result(timeout=_UNLOCK_TIMEOUT_SECONDS)
        except FutureTimeoutError as exc:
            raise CredentialUnavailableError(
                f"keyring did not respond within {_UNLOCK_TIMEOUT_SECONDS:.0f}s for service {service!r}"
            ) from exc
    if password is None:
        return None
    return username, password


def set_credential(service: str, username: str, password: str) -> None:
    """Stores both the username (under a fixed lookup key) and the password (keyed by that
    username) -- two keyring entries per service, since keyring.set_password only takes a
    (service, username) -> password shape and has no separate slot for "the username itself"."""
    keyring.set_password(service, _USERNAME_KEY, username)
    keyring.set_password(service, username, password)
