"""KB client. Talks to server.py over HTTP (port 25690). Falls back to direct
import if the server is down. Same method surface as before the socket->HTTP
migration, so embed.py/kb_cli/notes.py don't need to change."""

from typing import Any

import httpx

BASE_URL = "http://127.0.0.1:25690"
DEFAULT_TIMEOUT = 15  # seconds — without this, a wedged/slow server call hangs forever with
# no error and no way to notice, let alone recover


class KBServerTimeout(RuntimeError):
    """The server didn't respond within the timeout — it may be wedged. Check
    `journalctl --user -u kb.service` for the last logged command, and consider
    `scripts/service/restart`."""


class KBClient:
    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._client = httpx.Client(base_url=BASE_URL, timeout=timeout)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as e:
            raise KBServerTimeout(
                f"kb.service did not respond to {method} {path} within {self._client.timeout}s"
            ) from e
        except httpx.ConnectError as e:
            raise KBServerTimeout(f"kb.service is not reachable at {BASE_URL}") from e
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise RuntimeError(str(detail))
        return response.json()

    def ping(self) -> str:
        result = self._request("GET", "/ping")["result"]
        if not isinstance(result, str):
            raise RuntimeError(f"kb.service returned a non-string result: {result!r}")
        return result

    def embed(self, text: str) -> list[float]:
        result = self._request("POST", "/embed", json={"text": text})["result"]
        if not isinstance(result, list) or not all(isinstance(x, (int, float)) for x in result):
            raise RuntimeError(f"kb.service returned a non-vector result: {result!r}")
        return [float(x) for x in result]

    def search(self, query: str, collection: str) -> list[dict[str, Any]]:
        result = self._request("GET", "/search", params={"query": query, "collection": collection})
        if not isinstance(result, list) or not all(isinstance(x, dict) for x in result):
            raise RuntimeError(f"kb.service returned a non-list-of-objects result: {result!r}")
        return result

    def note_create(self, title: str, body: str, collection: str, tags: str | None = None) -> str:
        result = self._request(
            "POST", "/notes", json={"title": title, "body": body, "collection": collection, "tags": tags}
        )
        if not isinstance(result, str):
            raise RuntimeError(f"kb.service returned a non-string result: {result!r}")
        return result

    def note_update(
        self,
        id: int | None = None,
        find: str | None = None,
        title: str | None = None,
        body: str | None = None,
        tags: str | None = None,
        collection: str | None = None,
    ) -> str:
        if id is None and find is None:
            raise ValueError("id or find required")
        payload: dict[str, Any] = {
            "id": id,
            "find": find,
            "title": title,
            "body": body,
            "tags": tags,
            "collection": collection,
        }
        result = self._request("PATCH", "/notes", json=payload)
        if not isinstance(result, str):
            raise RuntimeError(f"kb.service returned a non-string result: {result!r}")
        return result

    def close(self) -> None:
        self._client.close()


def is_server_running() -> bool:
    try:
        httpx.get(f"{BASE_URL}/ping", timeout=1)
        return True
    except httpx.HTTPError:
        return False
