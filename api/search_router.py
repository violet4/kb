"""Search endpoint mirroring `kb search`: substring + semantic, ranked and de-duped
together by kb_cli/search.py's own search_all -- one implementation for the CLI and the
web UI. /info reports that implementation's parameters so the UI's explainer is
generated from them rather than restated."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.context_homes import contexts_by_tag
from api.deps import get_session
from api.record_hit import RecordHit, record_hit_fields
from kb_cli.search import (
    _SUBSTRING_DIST,
    _TEXT_COLUMNS,
    ALL_SEARCHABLE,
    MAX_SEMANTIC_DIST,
    SEMANTIC_SEARCHABLE,
    search_all,
)

router = APIRouter(prefix="/search-all")

DEFAULT_LIMIT = 20


class SearchHit(RecordHit):
    dist: float
    is_substring: bool


class SearchInfo(BaseModel):
    default_limit: int
    max_dist: float
    substring_models: list[str]
    substring_fields: list[str]
    semantic_models: list[str]


@router.get("/info", response_model=SearchInfo)
def search_info() -> SearchInfo:
    return SearchInfo(
        default_limit=DEFAULT_LIMIT,
        max_dist=MAX_SEMANTIC_DIST,
        substring_models=[m.__name__ for m in ALL_SEARCHABLE],
        substring_fields=list(_TEXT_COLUMNS),
        semantic_models=[m.__name__ for m in SEMANTIC_SEARCHABLE],
    )


@router.get("", response_model=list[SearchHit])
def search(
    q: str,
    limit: int = DEFAULT_LIMIT,
    max_dist: float = MAX_SEMANTIC_DIST,
    session: Session = Depends(get_session),
) -> list[SearchHit]:
    """`max_dist` bounds the semantic hits' cosine distance (the web UI's tolerance slider)."""
    by_tag = contexts_by_tag(session)
    return [
        SearchHit(**record_hit_fields(session, item, by_tag), dist=dist, is_substring=dist == _SUBSTRING_DIST)
        for item, dist in search_all(session, q, limit, max_dist=max_dist)
    ]
