"""KB client. Talks to server.py over Unix socket. Falls back to direct import if server is down."""
import json
import socket
from pathlib import Path
from typing import Any

SOCKET_PATH = Path(__file__).parent / "kb.sock"


class KBClient:
    def __init__(self):
        self._sock = None

    def _connect(self):
        if self._sock is not None:
            return
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(SOCKET_PATH))
        self._sock = sock
        self._file = sock.makefile("rwb")

    def _send(self, request: dict) -> dict:
        self._connect()
        self._file.write((json.dumps(request) + "\n").encode())
        self._file.flush()
        line = self._file.readline()
        return json.loads(line)

    def ping(self) -> str:
        r = self._send({"cmd": "ping"})
        return r["result"]

    def search(self, query: str, collection: str) -> list[dict]:
        r = self._send({"cmd": "search", "query": query, "collection": collection})
        if not r["ok"]:
            raise RuntimeError(r["error"])
        return r["result"]

    def note_create(self, title: str, body: str, collection: str, tags: str | None = None) -> str:
        r = self._send({"cmd": "note.create", "title": title, "body": body,
                        "collection": collection, "tags": tags})
        if not r["ok"]:
            raise RuntimeError(r["error"])
        return r["result"]

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None


def is_server_running() -> bool:
    return SOCKET_PATH.exists()
