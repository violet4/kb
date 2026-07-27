"""Embedding model singleton. Swap _MODEL_NAME + reembed to upgrade."""

import os
from typing import TYPE_CHECKING, Optional

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"
_model: Optional["SentenceTransformer"] = None


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
    from client import KBClient, is_server_running

    if is_server_running():
        return KBClient().embed(text)
    return _local_embed(text)
