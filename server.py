#!/usr/bin/env python3
"""KB persistent server. Keeps embedding model warm; exposes JSON over Unix socket.

Protocol: newline-delimited JSON.
  Request:  {"cmd": "ping"} | {"cmd": "embed", "text": "..."} | {"cmd": "search", "query": "...", "collection": "..."}
  Response: {"ok": true, "result": ...} | {"ok": false, "error": "..."}

Run:   uv run server.py
Stop:  kill $(cat data/kb.pid)  or  Ctrl-C
"""
import json
import logging
import os
import signal
import socketserver
import sys
import time
from pathlib import Path
from types import FrameType
from typing import Any

from models import Collection, Note, sess
from embed import _local_embed as embed, model_name

SOCKET_PATH = Path(__file__).parent / "data" / "kb.sock"
PID_PATH = Path(__file__).parent / "data" / "kb.pid"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("kb.server")


def _handle(request: dict[str, Any]) -> dict[str, Any]:
    cmd = request.get("cmd")

    if cmd == "ping":
        return {"ok": True, "result": f"pong model={model_name()}"}

    if cmd == "embed":
        text = request.get("text", "")
        vec = embed(text)
        return {"ok": True, "result": vec}

    if cmd == "search":
        query = request.get("query", "")
        col_str = request.get("collection")
        try:
            collection = Collection(col_str) if col_str else None
        except ValueError:
            return {"ok": False, "error": f"Unknown collection: {col_str!r}. Valid: {[c.value for c in Collection]}"}
        if collection is None:
            return {"ok": False, "error": "collection is required"}
        results = Note.search(query, collection)
        return {"ok": True, "result": [
            {"id": n.id, "title": n.title, "body": n.body, "collection": n.collection.value,
             "tags": n.tags, "dist": dist}
            for n, dist in results
        ]}

    if cmd == "note.create":
        col_str = request.get("collection")
        try:
            collection = Collection(col_str)
        except (ValueError, TypeError):
            return {"ok": False, "error": f"Unknown collection: {col_str!r}"}
        note = Note.create(
            title=request["title"],
            body=request["body"],
            collection=collection,
            tags=request.get("tags"),
        )
        sess.commit()
        return {"ok": True, "result": repr(note)}

    if cmd == "note.update":
        existing_note: Note | None
        if "id" in request:
            existing_note = Note.get(request["id"])
        elif "find" in request:
            existing_note = Note.find(request["find"])
        else:
            return {"ok": False, "error": "note.update requires 'id' or 'find'"}
        if existing_note is None:
            return {"ok": False, "error": "Note not found"}
        existing_note.update(
            title=request.get("title"),
            body=request.get("body"),
            tags=request.get("tags"),
        )
        sess.commit()
        return {"ok": True, "result": repr(existing_note)}

    return {"ok": False, "error": f"Unknown command: {cmd!r}"}


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        peer = self.client_address or "client"
        log.info("connection from %s", peer)
        try:
            for line in self.rfile:
                line = line.strip()
                if not line:
                    continue
                start = time.monotonic()
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    response = {"ok": False, "error": f"Invalid JSON: {e}"}
                else:
                    cmd = request.get("cmd")
                    log.info("cmd=%s start", cmd)
                    try:
                        response = _handle(request)
                    except Exception as e:
                        log.exception("cmd=%s error after %.3fs", cmd, time.monotonic() - start)
                        response = {"ok": False, "error": str(e)}
                    else:
                        log.info("cmd=%s done in %.3fs", cmd, time.monotonic() - start)
                self.wfile.write((json.dumps(response) + "\n").encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        log.info("connection closed")


class _Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    # ThreadingMixIn: `sess` is a scoped_session (thread-local), so this is safe, and it means
    # one slow/wedged request no longer blocks every other client indefinitely (previously a
    # single-threaded UnixStreamServer — see kb-engineering-17).
    allow_reuse_address = True
    daemon_threads = True


def _cleanup(signum: int | None = None, frame: FrameType | None = None) -> None:
    log.info("shutting down")
    SOCKET_PATH.unlink(missing_ok=True)
    PID_PATH.unlink(missing_ok=True)
    sys.exit(0)


def main() -> None:
    SOCKET_PATH.unlink(missing_ok=True)
    PID_PATH.write_text(str(os.getpid()))
    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)

    log.info("warming up embedding model...")
    embed("warmup")
    log.info("model ready: %s", model_name())

    log.info("listening on %s", SOCKET_PATH)
    with _Server(str(SOCKET_PATH), _Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
