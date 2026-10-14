"""One record as a list row in the web UI -- a search hit, or a record an agent session
touched -- so every list of mixed-type records links, places, and drags the same way."""

from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.context_homes import home_context_ids
from api.entities_router import ENTITY_TYPES
from archivebox_compat.config import ArchiveBoxConfigError
from context import placement_kind
from kb_cli.archivebox import archivebox_url
from models.context import Context
from models.knowledge.archived_link import ArchivedLink


class RecordHit(BaseModel):
    type: str
    id: int
    label: str
    drilldown: bool
    context_ids: list[int]  # contexts this record lives in (several for a tag-addressed row)
    # How the record can be moved by dropping it on a context: "parent" (a Context,
    # re-parented), "context"/"context_or_tag" (context.placement_kind), or None (no context).
    placement: Optional[str]
    original_url: Optional[str] = None
    archivebox_url: Optional[str] = None


def _label(item: Any) -> str:
    return (
        getattr(item, "title", None) or getattr(item, "name", None) or getattr(item, "description", None) or repr(item)
    )


def record_hit_fields(session: Session, item: Any, by_tag: dict[int, list[int]]) -> dict[str, Any]:
    """RecordHit's fields for item, for constructing RecordHit or any subclass of it."""
    original_url: Optional[str] = None
    ab_url: Optional[str] = None
    if isinstance(item, ArchivedLink):
        original_url = item.url
        if item.ab_id:
            try:
                ab_url = archivebox_url(session, f"archive/{item.ab_id}/")
            except ArchiveBoxConfigError:
                ab_url = None
    type_name = type(item).__name__
    return dict(
        type=type_name,
        id=item.id,
        label=_label(item),
        drilldown=type_name in ENTITY_TYPES,  # the types the entity page renders
        context_ids=home_context_ids(item, by_tag),
        placement="parent" if isinstance(item, Context) else placement_kind(type(item)),
        original_url=original_url,
        archivebox_url=ab_url,
    )
