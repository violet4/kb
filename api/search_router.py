"""Search endpoint mirroring `kb search`: substring + semantic, ranked and de-duped
together, over the same ALL_SEARCHABLE/SEMANTIC_SEARCHABLE model sets kb_cli/search.py
already defines -- reuses that module's search_entities/_semantic_hits directly rather
than reimplementing the ranking/dedup logic."""

import struct
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_session
from archivebox_compat.config import ArchiveBoxConfigError
from embed import embed
from kb_cli.archivebox import archivebox_url
from kb_cli.search import (
    ALL_SEARCHABLE,
    SEMANTIC_SEARCHABLE,
    _SUBSTRING_DIST,
    _semantic_hits,
    search_entities,
)
from models import ArchivedLink

router = APIRouter(prefix="/search-all")

# Maps a searchable model to the (entity_type, EntitySummary-compatible) identity the
# frontend's entity drilldown understands -- only models entities_router.ENTITY_TYPES
# also knows how to render get a type name here; others (Instruction, Context, Daily,
# ArchivedLink, Vendor, Item, LogEntry) are shown as plain search hits with no drilldown link.
_DRILLDOWN_TYPES = {"Goal", "Todo", "Wishlist", "Idea", "Note"}


class SearchHit(BaseModel):
    type: str
    id: int
    label: str
    dist: float
    is_substring: bool
    drilldown: bool
    original_url: Optional[str] = None
    archivebox_url: Optional[str] = None


def _label(item: Any) -> str:
    return (
        getattr(item, "title", None) or getattr(item, "name", None) or getattr(item, "description", None) or repr(item)
    )


def _to_hit(session: Session, item: Any, dist: float) -> SearchHit:
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
        original_url=original_url,
        archivebox_url=ab_url,
    )


@router.get("", response_model=list[SearchHit])
async def search_all(q: str, limit: int = 20, session: Session = Depends(get_session)) -> list[SearchHit]:
    substring_hits = search_entities(session, ALL_SEARCHABLE, q)
    scored: list[tuple[Any, float]] = [(item, _SUBSTRING_DIST) for item in substring_hits]

    raw = embed(q)
    vec = struct.pack(f"{len(raw)}f", *raw)
    for model in SEMANTIC_SEARCHABLE:
        scored.extend(_semantic_hits(model, session, q, limit, None, vec, include_done=False))

    best: dict[tuple[type, int], tuple[Any, float]] = {}
    for item, dist in scored:
        key = (type(item), item.id)
        if key not in best or dist < best[key][1]:
            best[key] = (item, dist)

    ranked = sorted(best.values(), key=lambda pair: pair[1])[:limit]
    return [_to_hit(session, item, dist) for item, dist in ranked]
