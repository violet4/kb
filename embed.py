"""Embedding model singleton. Swap _MODEL_NAME + reembed to upgrade."""

import os
from typing import TYPE_CHECKING, Optional

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"
_model: Optional["SentenceTransformer"] = None

# Set by server.py's own lifespan once it has warmed the model in-process. Lets embed()
# below skip entirely the "is the warm server running" HTTP self-check when this
# process *is* that server -- a synchronous httpx.get() back to 127.0.0.1:25690 from
# inside one of that same server's own single-threaded request handlers blocks the
# event loop from ever answering that /ping request, stalling every embed() call made
# during request handling (e.g. Event.create's reembed()) by about a second, observed
# via `time curl -X POST .../events`.
_warm_in_process = False


def mark_warm_in_process() -> None:
    global _warm_in_process
    _warm_in_process = True


def model_name() -> str:
    return _MODEL_NAME


def _local_embed(text: str) -> list[float]:
    # sentence_transformers pulls in torch -- a multi-second import cost. Deferred here
    # (rather than at module level) so the common warm-server path in embed() below never
    # pays it; only the fallback, when kb.service is actually down, needs it.
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_MODEL_NAME, local_files_only=True)
    result: list[float] = _model.encode(text).tolist()
    return result


def embed(text: str) -> list[float]:
    if _warm_in_process:
        return _local_embed(text)

    from client import KBClient, is_server_running

    if is_server_running():
        return KBClient().embed(text)
    return _local_embed(text)
