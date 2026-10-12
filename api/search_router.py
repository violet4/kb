"""Search endpoint mirroring `kb search`: substring + semantic, ranked and de-duped
together by kb_cli/search.py's own search_all -- one implementation for the CLI and the
web UI. /info reports that implementation's parameters so the UI's explainer is
generated from them rather than restated."""

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.context_homes import contexts_by_tag, home_context_ids
from api.deps import get_session
from archivebox_compat.config import ArchiveBoxConfigError
from kb_cli.archivebox import archivebox_url
from context import placement_kind
from kb_cli.search import (
    _SUBSTRING_DIST,
    _TEXT_COLUMNS,
    ALL_SEARCHABLE,
    MAX_SEMANTIC_DIST,
    SEMANTIC_SEARCHABLE,
    search_all,
)
from models import Context
from models import ArchivedLink

router = APIRouter(prefix="/search-all")

DEFAULT_LIMIT = 20

# Type names entities_router.ENTITY_TYPES also knows how to render -- a search hit of
# one of these gets a drilldown link into /entities/{type}/{id}; others (Context,
# Vendor, Item, LogEntry) are shown as plain search hits with no drilldown link.
_DRILLDOWN_TYPES = {"Goal", "Todo", "Wishlist", "Idea", "Note", "Instruction", "Daily", "ArchivedLink"}


class SearchHit(BaseModel):
    type: str
    id: int
    label: str
    dist: float
    is_substring: bool
    drilldown: bool
    context_ids: list[int]  # contexts this hit lives in (several for a tag-addressed row)
    # How the hit can be moved by dropping it on a context: "parent" (a Context, re-parented),
    # "context"/"context_or_tag" (context.placement_kind), or None (no context at all).
    placement: Optional[str]
    original_url: Optional[str] = None
    archivebox_url: Optional[str] = None


class SearchInfo(BaseModel):
    default_limit: int
    max_dist: float
    substring_models: list[str]
    substring_fields: list[str]
    semantic_models: list[str]


def _label(item: Any) -> str:
    return (
        getattr(item, "title", None) or getattr(item, "name", None) or getattr(item, "description", None) or repr(item)
    )


def _to_hit(session: Session, item: Any, dist: float, by_tag: dict[int, list[int]]) -> SearchHit:
    type_name = type(item).__name__
    original_url: Optional[str] = None
    ab_url: Optional[str] = None
    if isinstance(item, ArchivedLink):
        original_url = item.url
        if item.ab_id:
            try:
                ab_url = archivebox_url(session, f"archive/{item.ab_id}/")
            except ArchiveBoxConfigError:
                ab_url = None
    return SearchHit(
        type=type_name,
        id=item.id,
        label=_label(item),
        dist=dist,
        is_substring=dist == _SUBSTRING_DIST,
        drilldown=type_name in _DRILLDOWN_TYPES,
        context_ids=home_context_ids(item, by_tag),
        placement="parent" if isinstance(item, Context) else placement_kind(type(item)),
        original_url=original_url,
        archivebox_url=ab_url,
    )


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
    return [_to_hit(session, item, dist, by_tag) for item, dist in search_all(session, q, limit, max_dist=max_dist)]
