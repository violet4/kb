"""HasEmbedding: semantic search over a model's text, re-embedded on change."""

from __future__ import annotations

import enum
import struct
from typing import Any, Optional, Sequence

from sqlalchemy import String, Text, event, inspect, select
from sqlalchemy.orm import Mapped, Session, UOWTransaction, mapped_column

from models.behaviors.placement import HasContextOrTag
from models.context import Context
from models.db import _engine


class HasEmbedding:
    """Semantic-search support for any model. Subclasses implement `_embed_source_text()`
    (which fields feed the embedding) and get `.reembed()` plus a `.search(session, query,
    **filters)` classmethod for free. A `before_flush` listener below auto-reembeds any
    dirty instance whose source fields changed, so callers never need to call reembed()
    themselves after a plain attribute assignment -- only each model's own create() calls
    it directly, for the initial embed before the first flush. embedding_model is stored
    per-row so a model upgrade doesn't silently mix incomparable vectors -- search always
    filters to the current model_name()."""

    embedding_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    embedding: Mapped[Optional[bytes]] = mapped_column(Text, nullable=True)

    # Declared here type-only (no mapped_column) so mypy knows every subclass provides
    # them -- __tablename__/id come from the subclass's own Base/mapped_column, same
    # pattern as HasContextOrTag's context_id/context/tag above.
    __tablename__: str
    id: Mapped[int]

    @staticmethod
    def _embed_fields() -> set[str]:
        raise NotImplementedError

    def _embed_source_text(self) -> str:
        raise NotImplementedError

    def reembed(self) -> None:
        from embed import embed, model_name

        vec = embed(self._embed_source_text())
        self.embedding = struct.pack(f"{len(vec)}f", *vec)
        self.embedding_model = model_name()

    @classmethod
    def search(
        cls,
        session: Session,
        query: str,
        limit: int = 10,
        context: Optional[Context] = None,
        vec: Optional[bytes] = None,
        **filters: Any,
    ) -> list[tuple[Any, float]]:
        """`filters` are extra `column=value` equality clauses, e.g. collection=Collection.ENGINEERING.

        `context`, when given, restricts results to that context's subtree (plus no-context
        rows) using the same matching HasContextOrTag.matches_contexts expresses at the SQL
        layer for `list`/`tree`/substring search. This can't be expressed as an equality
        filter (it's an OR over context_id IN (...) / tag_id IN (...) / context_id IS NULL),
        so it's applied as a Python-side post-filter on a widened candidate set (10x limit,
        capped) pulled by nearest-distance first, then truncated back to `limit` -- keeps the
        common unscoped case a single exact query while still returning `limit` real matches
        in the scoped case rather than silently returning fewer once out-of-scope neighbors
        are dropped.

        `vec`, when given (the packed output of `embed_query()` below), is used instead of
        re-embedding `query` -- lets a caller that searches multiple models for the same query
        text (e.g. the top-level `kb search`) embed once and reuse the vector, rather than
        paying one embed() round-trip per model searched."""
        from embed import embed, model_name

        if vec is None:
            raw = embed(query)
            vec = struct.pack(f"{len(raw)}f", *raw)
        mn = model_name()
        table = cls.__tablename__
        where_clauses = ["embedding_model = ?", "deleted_at IS NULL"]
        params: list[Any] = [vec, mn]
        for col, value in filters.items():
            where_clauses.append(f"{col} = ?")
            params.append(value.name if isinstance(value, enum.Enum) else value)
        fetch_limit = min(limit * 10, 200) if context is not None else limit
        sql = (
            f"SELECT id, vec_distance_cosine(embedding, ?) AS dist FROM {table} "
            f"WHERE {' AND '.join(where_clauses)} ORDER BY dist ASC LIMIT {int(fetch_limit)}"
        )
        with _engine.connect() as conn:
            rows = conn.connection.execute(sql, params).fetchall()
        objs = {o.id: o for o in session.scalars(select(cls).where(cls.id.in_([r[0] for r in rows]))).all()}
        results = [(objs[r[0]], r[1]) for r in rows if r[0] in objs]
        if context is not None:
            in_scope = Context.self_and_descendants(session, context.name)
            context_ids = {c.id for c in in_scope}
            tag_ids = set(Context.active_tag_ids(in_scope))

            def _in_scope(obj: Any) -> bool:
                if isinstance(obj, HasContextOrTag):
                    return (
                        obj.context_id in context_ids
                        or obj.tag_id in tag_ids
                        or (obj.context_id is None and obj.tag_id is None)
                    )
                if hasattr(obj, "context_id"):
                    # A plain context_id (e.g. LogEntry), no tag support -- same
                    # "in scope or unset" rule as the HasContextOrTag case above.
                    return obj.context_id in context_ids or obj.context_id is None
                return True

            results = [(obj, dist) for obj, dist in results if _in_scope(obj)]
        return results[:limit]


@event.listens_for(Session, "before_flush")
def _reembed_dirty_has_embedding(
    session: Session, flush_context: UOWTransaction, instances: Optional[Sequence[Any]]
) -> None:
    for obj in session.dirty:
        if isinstance(obj, HasEmbedding):
            state = inspect(obj)
            assert state is not None
            changed = {attr.key for attr in state.attrs if attr.history.has_changes()}
            if changed & obj._embed_fields():
                obj.reembed()
