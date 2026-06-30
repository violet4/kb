"""Embedding model singleton. Swap _MODEL_NAME + reembed to upgrade."""
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def model_name() -> str:
    return _MODEL_NAME


def embed(text: str) -> list[float]:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME, local_files_only=True)
    return _model.encode(text).tolist()
