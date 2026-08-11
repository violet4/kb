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

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from api.core_router import router as core_router
from api.dailies_router import router as dailies_router
from embed import _local_embed as embed, model_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("kb.server")

PORT = 25690


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("warming up embedding model...")
    embed("warmup")
    log.info("model ready: %s", model_name())
    yield


app = FastAPI(title="kb server", lifespan=_lifespan)
app.include_router(core_router)
app.include_router(dailies_router)


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
