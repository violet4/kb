"""Which contexts a row shows up under -- shared by the context tree's counts and search
hits, so "where does this record live" has one answer in the web UI."""

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Context


def contexts_by_tag(session: Session) -> dict[int, list[int]]:
    """{tag_id: [ids of live contexts carrying that tag]}."""
    result: dict[int, list[int]] = defaultdict(list)
    for c in session.scalars(select(Context).where(Context.deleted_at.is_(None))):
        for tag in c.tags:
            result[tag.id].append(c.id)
    return result


def home_context_ids(row: Any, by_tag: dict[int, list[int]]) -> list[int]:
    """A Context is its own home; any other row lives in its context, or in every context
    carrying its tag (HasContextOrTag); a row with neither (e.g. a universal Instruction) has none."""
    if isinstance(row, Context):
        return [row.id]
    if getattr(row, "context_id", None) is not None:
        return [row.context_id]
    if getattr(row, "tag_id", None) is not None:
        return by_tag.get(row.tag_id, [])
    return []
