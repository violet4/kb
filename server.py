#!/usr/bin/env python3
"""KB persistent server. Keeps the embedding model warm; exposes JSON over HTTP.

One warm process, one port (25690), routers per feature -- same shape as
synth's `synth serve` (see ~/synth/scripts/synth_cli/music_search/server.py).
`core_router.py` holds the original embed/search/note endpoints (what used
to be a hand-rolled Unix-socket protocol, now plain HTTP so callers, the
future kbui frontend, and `curl` can all speak the same interface).

Run:   uv run server.py   (or via devserver.py, which restarts on .py changes)
Stop:  Ctrl-C, or `scripts/service/restart` for the systemd unit
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from api.archivebox_router import router as archivebox_router
from api.channels_router import router as channels_router
from api.core_router import router as core_router
from api.dailies_router import router as dailies_router
from api.entities_router import router as entities_router
from api.search_router import router as search_router
from api.sessions_router import router as sessions_router
from api.usage_router import router as usage_router
from embed import _local_embed as embed, model_name
from kb_cli.archivebox import resolve_or_push
from models import ArchivedLink, SessionFactory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("kb.server")

PORT = 25690


def _reconcile_stuck_archivebox_pushes() -> None:
    """Any ArchivedLink still PENDING/QUEUED at startup was either never picked up or was
    mid-flight when kb.service last stopped -- resolve_or_push's dedup-before-push check
    makes it safe to just resolve them now rather than leaving them to accumulate silently.
    Logs a summary either way, via journalctl --user -u kb.service, so a real failure surfaces
    at the next restart instead of being discovered months later as a pile of dead rows.

    Runs as a background asyncio task (see _lifespan below), not awaited before yield -- a
    handful of stuck rows can mean minutes of sequential ArchiveBox pushes (each one is a
    blocking ~15-20s+ call, see kb Note #105), and the server must start accepting requests
    immediately rather than making every other endpoint wait on that backlog draining first."""
    with SessionFactory() as session:
        stuck = ArchivedLink.stuck_mid_push(session)
        if not stuck:
            return
        ids = [link.id for link in stuck]
        log.warning("reconciling %d ArchivedLink row(s) stuck mid-push at startup: %s", len(ids), ids)
        succeeded: list[int] = []
        failed: list[int] = []
        for link in stuck:
            resolve_or_push(session, link)
            (succeeded if link.push_status.value == "success" else failed).append(link.id)
        log.warning(
            "startup reconciliation done: %d succeeded %s, %d failed %s -- see `kb ab show <id>` / `kb ab retry <id>`",
            len(succeeded),
            succeeded,
            len(failed),
            failed,
        )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("warming up embedding model...")
    embed("warmup")
    log.info("model ready: %s", model_name())
    reconcile_task = asyncio.create_task(asyncio.to_thread(_reconcile_stuck_archivebox_pushes))
    yield
    reconcile_task.cancel()


app = FastAPI(title="kb server", lifespan=_lifespan)
app.include_router(core_router)
app.include_router(dailies_router)
app.include_router(entities_router)
app.include_router(search_router)
app.include_router(archivebox_router)
app.include_router(usage_router)
app.include_router(sessions_router)
app.include_router(channels_router)


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
