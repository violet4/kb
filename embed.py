"""Embedding model singleton. Swap _MODEL_NAME + reembed to upgrade."""

import os

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def model_name() -> str:
    return _MODEL_NAME


def _local_embed(text: str) -> list[float]:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME, local_files_only=True)
    return _model.encode(text).tolist()


def embed(text: str) -> list[float]:
    from client import KBClient, is_server_running

    if is_server_running():
        return KBClient().embed(text)
    return _local_embed(text)
