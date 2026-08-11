"""Personal knowledge base ORM. Single SQLite database at ~/kb/data/kb.db."""

from __future__ import annotations

import enum
import struct
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, Sequence

import sqlite_vec  # type: ignore[import-untyped]  # no type stubs published for this package
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    or_,
    select,
)
from sqlalchemy.orm import (
    Mapped,
    MappedColumn,
    Session,
    UOWTransaction,
    mapped_column,
    object_session,
    relationship,
    sessionmaker,
    validates,
)
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm.base import NO_VALUE, NEVER_SET
from sqlalchemy.pool import ConnectionPoolEntry

from base import Base, _now
from mixins import HasUniqueName, HasWeight

_DB_PATH = Path(__file__).parent / "data" / "kb.db"
_engine = create_engine(f"sqlite:///{_DB_PATH}", echo=False)


@event.listens_for(_engine, "connect")
def _set_pragma(conn: DBAPIConnection, _: ConnectionPoolEntry) -> None:
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")


SessionFactory = sessionmaker(bind=_engine)


# ---------------------------------------------------------------------------
# Changelog + tracked_column
# ---------------------------------------------------------------------------


class ChangeLog(Base):
    __tablename__ = "changelog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_table: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    def __repr__(self) -> str:
        return f"<ChangeLog {self.entity_table}#{self.entity_id}.{self.field}: {self.old_value!r} → {self.new_value!r}>"


def tracked_column(*args: Any, **kwargs: Any) -> MappedColumn[Any]:
    """Drop-in for mapped_column that records changes to ChangeLog on assignment."""
    col = mapped_column(*args, **kwargs)
    col.column.info["tracked"] = True
    return col


def _on_tracked_set(target: Any, value: Any, oldvalue: Any, initiator: Any) -> None:
    if oldvalue is NO_VALUE or oldvalue is NEVER_SET:
        return
    if value == oldvalue:
        return
    session = object_session(target)
    if session is None:
        return
    table = target.__tablename__
    entity_id = target.id if target.id is not None else -1
    entry = ChangeLog(
        entity_table=table,
        entity_id=entity_id,
        field=initiator.key,
        old_value=str(oldvalue) if oldvalue is not None else None,
        new_value=str(value) if value is not None else None,
    )
    session.add(entry)


def _register_tracked_listeners(mapper: Any, cls: Any) -> None:
    for attr_name, col_prop in mapper.columns.items():
        if col_prop.info.get("tracked"):
            attr = getattr(cls, attr_name)
            event.listen(attr, "set", _on_tracked_set)


event.listen(Base, "mapper_configured", _register_tracked_listeners, propagate=True)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Collection(enum.Enum):
    ENGINEERING = "engineering"
    PERSONAL = "personal"
    GORGON = "gorgon"
    WORK = "work"

    ALL = "all"  # search-only sentinel — not a valid storage collection


class PersonTier(enum.Enum):
    CLOSE = "close"
    ACQUAINTANCE = "acquaintance"
    PUBLIC_FIGURE = "public_figure"


class GoalStatus(enum.Enum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class TodoStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DROPPED = "dropped"


class WishlistStatus(enum.Enum):
    ACTIVE = "active"
    ACQUIRED = "acquired"
    DROPPED = "dropped"


class IdeaStatus(enum.Enum):
    ACTIVE = "active"  # sitting in someday/maybe, revisited only on deliberate review
    PROMOTED = "promoted"  # became a real Goal/Todo/Wishlist item (see Journal for which)
    DROPPED = "dropped"


class DailyTier(enum.Enum):
    CRITICAL = "critical"  # always surfaces in summary until completed today
    OPTIONAL = "optional"  # hidden by default, needs an explicit request (e.g. kb daily list --all)


class WishlistEffort(enum.Enum):
    GRAB = "grab"  # next time you're out
    RESEARCH = "research"  # needs investigation before buying
    PROJECT = "project"  # multi-step effort (e.g. server upgrade)


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


class Context(Base, HasUniqueName):
    """A GTD-style location/situation node (e.g. "pg" -> "Serbule Hills" -> "Serbule Hills
    Tavern") -- where/with-what an item is actionable. Single-parent tree via parent_id
    (adjacency list): every node has at most one parent, matching the physical reality that
    a place lives in exactly one broader place. See Tag for the orthogonal "what kind of
    place is this" facet (a Context can carry several Tags, e.g. two different taverns both
    tagged "tavern"), which is how a Todo like "buy salt" surfaces under any tavern without
    being pinned to one."""

    __tablename__ = "context"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)

    parent: Mapped[Optional[Context]] = relationship("Context", remote_side=[id])
    tags: Mapped[list["Tag"]] = relationship("Tag", secondary="context_tag")

    @classmethod
    def get_or_create(cls, session: Session, name: str, description: Optional[str] = None) -> Context:
        obj = session.scalars(select(cls).filter_by(name=name)).one_or_none()
        if obj is None:
            obj = cls(name=name, description=description)
            session.add(obj)
            session.flush()
        return obj

    @classmethod
    def get_existing(cls, session: Session, name: str) -> Context:
        """Look up a context by name, raising rather than silently creating one --
        use this for switching/filtering, where a typo'd name should be a hard error,
        not a new, accidental Context row. Use get_or_create only for the explicit
        `context add` path, where creating a new Context is the intended action."""
        obj = session.scalars(select(cls).filter_by(name=name)).one_or_none()
        if obj is None:
            raise ValueError(f"no such context: {name!r} (create it with: kb context add {name!r})")
        return obj

    def ancestors(self) -> list[Context]:
        """This context plus every parent up the chain, broadest last."""
        chain = [self]
        node = self
        while node.parent is not None:
            node = node.parent
            chain.append(node)
        return chain

    @classmethod
    def self_and_descendants(cls, session: Session, name: str) -> Sequence[Context]:
        """`name` itself plus every context reachable by walking parent_id downward
        (e.g. "pg" matches "pg", "pg"'s children, their children, ...)."""
        root = cls.get_existing(session, name)
        all_contexts = session.scalars(select(cls)).all()
        by_parent: dict[Optional[int], list[Context]] = {}
        for c in all_contexts:
            by_parent.setdefault(c.parent_id, []).append(c)

        result = [root]
        frontier = [root]
        while frontier:
            next_frontier = []
            for node in frontier:
                next_frontier.extend(by_parent.get(node.id, []))
            result.extend(next_frontier)
            frontier = next_frontier
        return result

    @classmethod
    def active_tag_ids(cls, contexts: Sequence[Context]) -> list[int]:
        """Every Tag id carried by any Context in `contexts` (e.g. from
        self_and_descendants) -- the set a tag_id-addressed Goal/Todo/Daily/Idea
        must match to surface under this context subtree. See HasContextOrTag."""
        ids: set[int] = set()
        for c in contexts:
            ids.update(t.id for t in c.tags)
        return list(ids)

    def __repr__(self) -> str:
        parent_str = f" -> {self.parent.name}" if self.parent else ""
        return f"<Context {self.name!r}{parent_str}>"


class Tag(Base, HasUniqueName):
    """A flat, non-hierarchical label for "what kind of place/thing is this"
    (e.g. "tavern") -- orthogonal to Context's tree. A Context can carry several
    Tags (context_tag, many-to-many); Goal/Todo/Daily/Idea can carry at most one
    Tag, mutually exclusive with having a context_id (see each entity's validation).
    A tagged, context-free item (e.g. "buy salt" tagged "tavern") surfaces under
    any active Context whose subtree contains a Context carrying that same Tag,
    without being pinned to one specific place."""

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    def __repr__(self) -> str:
        return f"<Tag {self.name!r}>"


class ContextTag(Base):
    __tablename__ = "context_tag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    context_id: Mapped[int] = mapped_column(Integer, ForeignKey("context.id"), nullable=False)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tag.id"), nullable=False)


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
        where_clauses = ["embedding_model = ?"]
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


class HasContextOrTag:
    """A single tag_id, mutually exclusive with the entity's own context_id: a Goal/Todo/Daily/
    Idea is either pinned to one place (context_id) or floats to anywhere carrying a matching
    Tag (tag_id), never both -- see Context/Tag docstrings for why. Composed alongside each
    entity's own context_id column, which predates this mixin and stays entity-local -- declared
    here too (Optional[int], no mapped_column) purely so mypy knows every subclass provides it;
    the real column comes from the subclass's own mapped_column(..., ForeignKey("context.id")).
    context/tag (the relationship attributes, not the _id FK columns) are declared the same
    type-only way, so shared helpers (e.g. kb_cli._util.apply_context_or_tag_update) can assign
    through the mixin type -- the real relationship() comes from each subclass."""

    tag_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tag.id"), nullable=True)
    context_id: Mapped[Optional[int]]
    context: Mapped[Optional[Context]]
    tag: Mapped[Optional["Tag"]]

    @validates("tag_id")
    def _validate_tag_id(self, key: str, value: Optional[int]) -> Optional[int]:
        if value is not None and getattr(self, "context_id", None) is not None:
            raise ValueError(f"{type(self).__name__}: context_id and tag_id are mutually exclusive")
        return value

    @validates("context_id")
    def _validate_context_id(self, key: str, value: Optional[int]) -> Optional[int]:
        if value is not None and getattr(self, "tag_id", None) is not None:
            raise ValueError(f"{type(self).__name__}: context_id and tag_id are mutually exclusive")
        return value

    @classmethod
    def matches_contexts(cls, contexts: Sequence[Context]) -> Any:
        """The one 'is this row addressable from this set of Contexts' expression --
        true for a row pinned to one of these contexts directly (context_id), or floating
        via a tag_id any of these contexts carries (see Tag docstring). Every caller that
        needs this match (a subtree-scoped .active() query, a single-node tree render) should
        go through this instead of re-deriving the context_id/tag_id OR by hand."""
        ids = [c.id for c in contexts]
        tag_ids = Context.active_tag_ids(contexts)
        return cls.context_id.in_(ids) | cls.tag_id.in_(tag_ids)


class Instruction(Base, HasContextOrTag, HasEmbedding):
    """A node in the topic tree of durable guidance -- unifies what would otherwise be scattered
    across CLAUDE.md files, Claude Code skills, and Claude Code memory into one structure. Single-
    parent tree via parent_id (adjacency list), same shape as Context but a SEPARATE tree: Context
    is where something is actionable (e.g. "pg" -> "Serbule Hills Tavern"); Instruction's parent_id
    tree is what topic something belongs to (e.g. "engineering" -> "react" -> "dnd-kit"), independent
    of place. A node can optionally also carry a context_id/tag_id (via HasContextOrTag) to link it
    into the Context tree when it's genuinely tied to a place, not just a topic (e.g. NPC lore that
    should surface automatically when Context walks into that location).

    trigger is the whole loading mechanism: null means the node is unconditionally relevant to
    anyone who reaches it by tree traversal (its body loads automatically). Non-null means only the
    short trigger string surfaces by default when the node is reached -- the full body is a separate,
    deliberate fetch, made only once the trigger's condition actually matches what's being worked on.
    There is no separate "trigger tree" -- a trigger-worded node's children ARE topic-tree navigation,
    just phrased as conditions ("whenever doing a merge") instead of topic names ("merge").

    Intended navigation is root-to-leaf, one level at a time, judgment-based (which of this level's
    handful of children is obviously relevant), not a search/similarity operation -- keep each node's
    children few enough (~5-10) that this stays cheap; restructure (insert an intermediate node)
    rather than letting any level's fanout grow past that. See kb Goal #23 for full design rationale.

    This is the one table meant for shareable, git-trackable export (a design in progress as of
    2026-07 -- see Goal #23) -- unlike Note (a personal notebook), Instruction's content is
    operational reference documentation, genuinely useful to someone else running this system."""

    __tablename__ = "instruction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("instruction.id"), nullable=True)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)

    parent: Mapped[Optional[Instruction]] = relationship("Instruction", remote_side=[id])
    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional["Tag"]] = relationship("Tag")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "body"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.body}"

    @classmethod
    def roots(cls, session: Session) -> Sequence[Instruction]:
        """Top-level nodes (no parent) -- the entry points to the tree."""
        return session.scalars(select(cls).where(cls.parent_id.is_(None))).all()

    @classmethod
    def children(cls, session: Session, parent_id: int) -> Sequence[Instruction]:
        """Direct children of a node, for one level of tree expansion."""
        return session.scalars(select(cls).where(cls.parent_id == parent_id)).all()

    def __repr__(self) -> str:
        trigger_note = f" trigger={self.trigger!r}" if self.trigger else ""
        return f"<Instruction #{self.id} {self.title!r}{trigger_note}>"


class Settings(Base):
    """Single-row table (id=1) for small standalone config values that don't belong on any
    other model. Start here before adding a dedicated settings table for a new value."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_boundary_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notifications_muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notifications_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    @classmethod
    def get(cls, session: Session) -> Settings:
        row = session.scalars(select(cls).filter_by(id=1)).one_or_none()
        if row is None:
            row = cls(id=1)
            session.add(row)
            session.flush()
        return row

    def resolved_timezone(self) -> ZoneInfo:
        """The IANA zone to use: an explicit override if set, else auto-detected from
        /etc/localtime (Linux's standard symlink to the system's zoneinfo file)."""
        if self.timezone:
            return ZoneInfo(self.timezone)
        localtime = Path("/etc/localtime")
        if localtime.is_symlink():
            target = str(localtime.resolve())
            marker = "zoneinfo/"
            if marker in target:
                return ZoneInfo(target.split(marker, 1)[1])
        return ZoneInfo("UTC")

    def __repr__(self) -> str:
        return f"<Settings day_boundary_hour={self.day_boundary_hour}>"


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[PersonTier] = mapped_column(
        Enum(PersonTier, create_constraint=True, validate_strings=True), nullable=False, default=PersonTier.ACQUAINTANCE
    )
    closeness: Mapped[int] = tracked_column(Integer, nullable=False, default=0)
    last_contacted: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reach_out_every_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @classmethod
    def get(cls, session: Session, name: str) -> Optional[Person]:
        return session.scalars(select(cls).filter_by(name=name)).one_or_none()

    @classmethod
    def get_or_create(cls, session: Session, name: str, tier: PersonTier = PersonTier.ACQUAINTANCE) -> Person:
        obj = cls.get(session, name)
        if obj is None:
            obj = cls(name=name, tier=tier)
            session.add(obj)
            session.flush()
        return obj

    @classmethod
    def in_my_life(cls, session: Session) -> Sequence[Person]:
        """People who are part of my immediate surrounding life (excludes public figures)."""
        return session.scalars(
            select(cls).where(cls.tier != PersonTier.PUBLIC_FIGURE).order_by(cls.closeness.desc())
        ).all()

    @classmethod
    def overdue_for_contact(cls, session: Session) -> list[Person]:
        """People I should have reached out to by now, ordered by most overdue."""
        now = _now()
        candidates = session.scalars(
            select(cls).where(cls.tier != PersonTier.PUBLIC_FIGURE).where(cls.reach_out_every_days.isnot(None))
        ).all()
        overdue: list[tuple[Person, Optional[int]]] = []
        for p in candidates:
            if p.last_contacted is None:
                overdue.append((p, None))
            else:
                last = (
                    p.last_contacted.replace(tzinfo=timezone.utc)
                    if p.last_contacted.tzinfo is None
                    else p.last_contacted
                )
                days_since = (now - last).days
                assert p.reach_out_every_days is not None  # guaranteed by the isnot(None) filter above
                if days_since >= p.reach_out_every_days:
                    overdue.append((p, days_since))
        overdue.sort(key=lambda x: (x[1] is None, -(x[1] or 0)))
        return [p for p, _ in overdue]

    def __repr__(self) -> str:
        return f"<Person {self.name!r} [{self.tier.value}] closeness={self.closeness}>"


# ---------------------------------------------------------------------------
# HasEmbedding (RAG)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Goal
# ---------------------------------------------------------------------------


class Goal(Base, HasContextOrTag, HasEmbedding):
    __tablename__ = "goal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[GoalStatus] = tracked_column(
        Enum(GoalStatus, create_constraint=True, validate_strings=True), nullable=False, default=GoalStatus.ACTIVE
    )
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional[Tag]] = relationship("Tag")
    todos: Mapped[list[Todo]] = relationship("Todo", back_populates="goal")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "description", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.description or ''}\n\n{self.notes or ''}"

    @classmethod
    def active(
        cls,
        session: Session,
        context: Optional[Context] = None,
        contexts: Optional[Sequence[Context]] = None,
        include_no_context: bool = False,
    ) -> Sequence[Goal]:
        """`context` matches that single context exactly; `contexts` (e.g. from
        Context.self_and_descendants) matches any context in the given set, plus any
        Goal whose tag_id is carried by a Context in that set (see HasContextOrTag) --
        use the latter for a context-plus-sub-contexts filter. include_no_context also
        surfaces Goals with no context/tag at all (e.g. for a summary view that treats
        untagged items as always-relevant, regardless of which context is active)."""
        q = select(cls).where(cls.status == GoalStatus.ACTIVE)
        if context is not None:
            q = q.where(cls.context_id == context.id)
        if contexts is not None:
            matches = cls.matches_contexts(contexts)
            q = (
                q.where(matches | (cls.context_id.is_(None) & cls.tag_id.is_(None)))
                if include_no_context
                else q.where(matches)
            )
        return session.scalars(q).all()

    @classmethod
    def create(
        cls,
        session: Session,
        title: str,
        description: Optional[str] = None,
        context: Optional[Context] = None,
        notes: Optional[str] = None,
    ) -> Goal:
        goal = cls(title=title, description=description, context_id=context.id if context else None, notes=notes)
        goal.reembed()
        session.add(goal)
        session.flush()
        return goal

    def __repr__(self) -> str:
        size = len(self.title) + len(self.description or "") + len(self.notes or "")
        return f"<Goal #{self.id} {self.title!r} [{self.status.value}] {size}b>"


# ---------------------------------------------------------------------------
# Todo
# ---------------------------------------------------------------------------


class Todo(Base, HasContextOrTag, HasEmbedding):
    __tablename__ = "todo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[TodoStatus] = tracked_column(
        Enum(TodoStatus, create_constraint=True, validate_strings=True), nullable=False, default=TodoStatus.PENDING
    )
    goal_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("goal.id"), nullable=True)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    blocked_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("todo.id"), nullable=True)
    effort: Mapped[Optional[WishlistEffort]] = mapped_column(
        Enum(WishlistEffort, create_constraint=True, validate_strings=True), nullable=True
    )
    defer_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    goal: Mapped[Optional[Goal]] = relationship("Goal", back_populates="todos")
    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional[Tag]] = relationship("Tag")
    blocked_by: Mapped[Optional[Todo]] = relationship("Todo", remote_side=[id])

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.notes or ''}"

    @classmethod
    def active(
        cls,
        session: Session,
        context: Optional[Context] = None,
        contexts: Optional[Sequence[Context]] = None,
        include_no_context: bool = False,
        effort: Optional[WishlistEffort] = None,
        include_deferred: bool = False,
    ) -> Sequence[Todo]:
        """`context` matches that single context exactly; `contexts` (e.g. from
        Context.self_and_descendants) matches any context in the given set, plus any
        Todo whose tag_id is carried by a Context in that set (see HasContextOrTag) --
        use the latter for a context-plus-sub-contexts filter. include_no_context also
        surfaces Todos with no context/tag at all (e.g. for a summary view that treats
        untagged items as always-relevant, regardless of which context is active).
        Named to match Goal/Daily/Idea's own .active() -- every context/tag-addressable
        entity exposes the same shape so a generic renderer can call it uniformly."""
        q = select(cls).where(cls.status.in_([TodoStatus.PENDING, TodoStatus.IN_PROGRESS]))
        if context is not None:
            q = q.where(cls.context_id == context.id)
        if contexts is not None:
            matches = cls.matches_contexts(contexts)
            q = (
                q.where(matches | (cls.context_id.is_(None) & cls.tag_id.is_(None)))
                if include_no_context
                else q.where(matches)
            )
        if effort is not None:
            q = q.where(cls.effort == effort)
        if not include_deferred:
            q = q.where((cls.defer_until.is_(None)) | (cls.defer_until <= _now()))
        return session.scalars(q).all()

    @classmethod
    def urgent_pending(cls, session: Session) -> Sequence[Todo]:
        """Urgent Todos still pending, ignoring context/tag scope and defer_until --
        the one query behind kb summary's unconditional URGENT section, so an urgent
        item can never be filtered out by context switching or a future due date."""
        q = select(cls).where(cls.urgent.is_(True), cls.status.in_([TodoStatus.PENDING, TodoStatus.IN_PROGRESS]))
        return session.scalars(q).all()

    @classmethod
    def create(
        cls,
        session: Session,
        title: str,
        goal: Optional[Goal] = None,
        context: Optional[Context] = None,
        tag: Optional[Tag] = None,
        notes: Optional[str] = None,
        blocked_by: Optional[Todo] = None,
        effort: Optional[WishlistEffort] = None,
        defer_until: Optional[datetime] = None,
        urgent: bool = False,
    ) -> Todo:
        todo = cls(
            title=title,
            goal_id=goal.id if goal else None,
            context_id=context.id if context else None,
            tag_id=tag.id if tag else None,
            notes=notes,
            blocked_by_id=blocked_by.id if blocked_by else None,
            effort=effort,
            defer_until=defer_until,
            urgent=urgent,
        )
        todo.reembed()
        session.add(todo)
        session.flush()
        return todo

    def __repr__(self) -> str:
        effort_str = f" ({self.effort.value})" if self.effort else ""
        defer_str = f" defer_until={self.defer_until.strftime('%Y-%m-%d %H:%M')}" if self.defer_until else ""
        context_str = f" [{self.context.name}]" if self.context else ""
        tag_str = f" @{self.tag.name}" if self.tag else ""
        urgent_str = " !URGENT!" if self.urgent else ""
        return (
            f"<Todo #{self.id} {self.title!r} [{self.status.value}]{effort_str}{defer_str}"
            f"{context_str}{tag_str}{urgent_str}>"
        )


# ---------------------------------------------------------------------------
# Daily
# ---------------------------------------------------------------------------


class Daily(Base, HasContextOrTag):
    """A recurring/optional item — distinct from Goal (a purpose/end-state) and Todo (a step toward one).

    domain ("irl"/"pg", mirrors Vendor.domain) separates life-maintenance dailies from game dailies.
    tier controls default summary visibility: CRITICAL always surfaces until completed today,
    OPTIONAL stays hidden unless explicitly requested.

    recurrence is a required cadence rule (grammar below) -- every Daily has one, so completing it
    always computes and stores next_due_date, making "is this due" a plain date comparison
    rather than recomputed day-boundary math. next_due_date is the single source of truth for when
    a Daily is next due; there is no separate "last completed" record, since only the upcoming due
    date is ever queried, not completion history.

    next_due_date is a calendar date, not a timestamp -- a Daily's due-ness is a day-cycle question
    ("which day-boundary window is this due in"), never a sub-day one, so the field only ever needs
    to answer "is today's day-cycle at or past this date." day_boundary_hour/timezone convert
    "now" to a day-cycle date once, via _current_day(); nothing downstream needs an instant.

    Recurrence grammar:
      "daily"        -- due again at the next day-boundary after completion.
      "every:N"      -- due again N days after completion (e.g. "every:2" for alternating-day items).
      "weekly:DAY"   -- due again on the next occurrence of DAY ("MON".."SUN") after completion.
      "monthly:D"    -- due again on day D of the next applicable month after completion (D 1-28).
      "yearly:MM-DD" -- due again on month MM day DD of the next applicable year after completion
                        (e.g. "yearly:07-23" for a July 23 birthday/anniversary).

    show_after_hour (0-23, local time) is applied after next_due_date decides a Daily is due "today"
    -- it further hides a Daily that's due today (but not yet overdue) from due()/summary until
    that local hour, so evening-only items (e.g. "shower before bed") don't clutter the morning
    view. Once overdue (next_due_date has fully passed), show_after_hour no longer applies.

    remind_days_before (default 0) widens visibility to start that many days ahead of
    next_due_date -- for a yearly reminder (e.g. a birthday) that needs advance notice to be
    actionable (buy a gift, plan a call), not just same-day visibility. It only affects when a
    Daily first becomes visible; is_overdue/complete/catch_up stay anchored on next_due_date,
    unaffected. show_after_hour does not apply inside the lead-in window (an hour-of-day gate
    doesn't compose meaningfully across multiple days) -- it only gates on the due day itself.
    """

    __tablename__ = "daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    domain: Mapped[str] = mapped_column(String, nullable=False, default="irl")
    tier: Mapped[DailyTier] = mapped_column(
        Enum(DailyTier, create_constraint=True, validate_strings=True), nullable=False, default=DailyTier.CRITICAL
    )
    recurrence: Mapped[str] = mapped_column(String, nullable=False, default="daily")
    show_after_hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    remind_days_before: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional[Tag]] = relationship("Tag")

    _WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

    @classmethod
    def _current_day(cls, session: Session, now: datetime) -> date:
        """Which day-cycle "now" falls in, as a plain date -- computed by applying
        Settings.day_boundary_hour in local time (not UTC), so a late local bedtime
        doesn't get treated as already past a UTC-midnight-adjacent cutoff. This is
        the only place day_boundary_hour/timezone are ever consulted; every other
        Daily method compares dates that are already resolved to day-cycles."""
        settings = Settings.get(session)
        local_now = now.astimezone(settings.resolved_timezone())
        local_day_start = local_now.replace(hour=settings.day_boundary_hour, minute=0, second=0, microsecond=0)
        if local_now < local_day_start:
            local_day_start -= timedelta(days=1)
        return local_day_start.date()

    @classmethod
    def active(
        cls,
        session: Session,
        context: Optional[Context] = None,
        contexts: Optional[Sequence[Context]] = None,
        include_no_context: bool = False,
    ) -> Sequence[Daily]:
        """`context` matches that single context exactly; `contexts` (e.g. from
        Context.self_and_descendants) matches any context in the given set, plus any
        Daily whose tag_id is carried by a Context in that set (see HasContextOrTag)."""
        q = select(cls).where(cls.is_active.is_(True))
        if context is not None:
            q = q.where(cls.context_id == context.id)
        if contexts is not None:
            matches = cls.matches_contexts(contexts)
            q = (
                q.where(matches | (cls.context_id.is_(None) & cls.tag_id.is_(None)))
                if include_no_context
                else q.where(matches)
            )
        return session.scalars(q).all()

    def is_overdue(self, session: Session) -> bool:
        """True once today's day-cycle is past the one this Daily was due in --
        e.g. litter due Monday (and shown from show_after_hour onward) is fine
        through the rest of Monday, then becomes overdue right at Tuesday's
        day-boundary, the moment the day it should have been done in has closed."""
        today = self._current_day(session, _now())
        return today > self.next_due_date

    def is_due_now(self, session: Session) -> bool:
        """True once today's day-cycle has reached next_due_date minus
        remind_days_before (0 by default, i.e. exactly next_due_date), gated by
        show_after_hour (0-23 local) so evening-only items don't surface in the
        morning -- but only on the day it first became due, never inside a
        remind_days_before lead-in window. Once is_overdue() is true the item has
        already missed its day entirely, so show_after_hour no longer applies: an
        overdue "shower before bed" must stay visible all day, not just evenings."""
        today = self._current_day(session, _now())
        window_start = self.next_due_date - timedelta(days=self.remind_days_before)
        if today < window_start:
            return False
        if self.show_after_hour is not None and today == self.next_due_date:
            settings = Settings.get(session)
            local_hour = _now().astimezone(settings.resolved_timezone()).hour
            if local_hour < self.show_after_hour:
                return False
        return True

    @classmethod
    def due(cls, session: Session, domain: Optional[str] = None, tier: Optional[DailyTier] = None) -> list[Daily]:
        """Active dailies currently due, per is_due_now()."""
        q = select(cls).where(cls.is_active.is_(True))
        if domain is not None:
            q = q.where(cls.domain == domain)
        if tier is not None:
            q = q.where(cls.tier == tier)
        dailies = session.scalars(q).all()
        return [d for d in dailies if d.is_due_now(session)]

    @classmethod
    def create(
        cls,
        session: Session,
        description: str,
        context: Optional[Context] = None,
        tag: Optional[Tag] = None,
        domain: str = "irl",
        tier: DailyTier = DailyTier.CRITICAL,
        recurrence: str = "daily",
        show_after_hour: Optional[int] = None,
        location: Optional[str] = None,
        remind_days_before: int = 0,
        notes: Optional[str] = None,
    ) -> Daily:
        daily = cls(
            description=description,
            context_id=context.id if context else None,
            tag_id=tag.id if tag else None,
            domain=domain,
            tier=tier,
            recurrence=recurrence,
            show_after_hour=show_after_hour,
            location=location,
            remind_days_before=remind_days_before,
            notes=notes,
        )
        # Seed as due today, not one recurrence step back through _compute_next_due
        # -- that only lands on "already due" for the daily cadence; every:N>1/
        # weekly/monthly would land a full period in the future.
        daily.next_due_date = daily._current_day(session, _now())
        session.add(daily)
        session.flush()
        return daily

    def _compute_next_due(self, session: Session, after: date) -> date:
        """The next due date per this Daily's recurrence rule."""
        kind, _, arg = self.recurrence.partition(":")

        if kind == "daily" or not kind:
            return after + timedelta(days=1)
        elif kind == "every":
            return after + timedelta(days=int(arg))
        elif kind == "weekly":
            target = Daily._WEEKDAYS.index(arg.upper())
            days_ahead = (target - after.weekday()) % 7
            days_ahead = days_ahead or 7
            return after + timedelta(days=days_ahead)
        elif kind == "monthly":
            day = int(arg)
            year, month = after.year, after.month + 1
            if month > 12:
                month = 1
                year += 1
            return after.replace(year=year, month=month, day=day)
        elif kind == "yearly":
            month_str, _, day_str = arg.partition("-")
            month, day = int(month_str), int(day_str)
            year = after.year
            if (month, day) <= (after.month, after.day):
                year += 1
            return date(year, month, day)
        else:
            raise ValueError(f"unknown recurrence kind: {kind!r}")

    def complete(self, session: Session) -> None:
        """Advance next_due_date one recurrence step past the day being completed --
        anchored on next_due_date itself, not on today's date, so completing something
        late (after its day closed) still lands on the very next occurrence rather than
        skipping ahead an extra step because of how late the completion happened."""
        self.next_due_date = self._compute_next_due(session, self.next_due_date)

    def catch_up(self, session: Session) -> None:
        """Advance next_due_date forward through however many missed days have
        elapsed, landing on the first occurrence that isn't overdue -- for a Daily
        that's been neglected for multiple cycles, rather than requiring complete()
        to be called once per missed day."""
        while self.is_overdue(session):
            self.next_due_date = self._compute_next_due(session, self.next_due_date)

    def __repr__(self) -> str:
        return f"<Daily #{self.id} {self.description!r}>"


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------


class Item(Base):
    """JTI base for game-specific items. Game side tables below join 1:1 via id, each composing
    whichever mixins.py traits it actually needs (weight, grid size, stack size, ...)."""

    __tablename__ = "item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    upc: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")

    __mapper_args__ = {"polymorphic_on": "game", "polymorphic_identity": "item"}

    @classmethod
    def by_game(cls, session: Session, game: str) -> Sequence[Item]:
        return session.scalars(select(cls).filter_by(game=game)).all()

    def __repr__(self) -> str:
        return f"<Item #{self.id} {self.name!r} [{self.game}]>"


class IrlItem(Item, HasWeight):
    """Real-world items — groceries, household goods, etc. Tracked the same way as game
    items (Vendor/VendorItem/Purchase apply equally): we can never see a store's whole
    price history at once, only snippets over time, same as an in-game player market."""

    __tablename__ = "irl_item"

    id: Mapped[int] = mapped_column(Integer, ForeignKey("item.id"), primary_key=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # free text, e.g. "5.5oz can"

    __mapper_args__ = {"polymorphic_identity": "irl"}


# ---------------------------------------------------------------------------
# Vendor / VendorItem / Purchase — price/quantity history for anything
# transactable, real or in-game. A grocery store and a PG player-shop NPC
# are both "somewhere you buy Items from"; domain distinguishes them.
# ---------------------------------------------------------------------------


class Vendor(Base):
    __tablename__ = "vendor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)  # "irl", "pg", ...
    kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # e.g. "grocery", "npc", "player_shop"
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Vendor {self.name!r} [{self.domain}]>"


class VendorItem(Base):
    """A vendor's own code for an Item — may differ from Item.upc (store-internal SKU vs.
    universal barcode), and differs vendor to vendor for the same Item."""

    __tablename__ = "vendor_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(Integer, ForeignKey("vendor.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("item.id"), nullable=False)
    vendor_sku: Mapped[str] = mapped_column(String, nullable=False)

    vendor: Mapped[Vendor] = relationship("Vendor")
    item: Mapped[Item] = relationship("Item")

    __table_args__ = (UniqueConstraint("vendor_id", "vendor_sku"),)

    def __repr__(self) -> str:
        return f"<VendorItem {self.vendor.name if self.vendor else '?'}:{self.vendor_sku} -> {self.item.name if self.item else '?'}>"


class Purchase(Base):
    __tablename__ = "purchase"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("vendor_item.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=1)
    unit_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    total_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    vendor_item: Mapped[VendorItem] = relationship("VendorItem")

    def __repr__(self) -> str:
        return (
            f"<Purchase {self.quantity}x {self.vendor_item.item.name if self.vendor_item else '?'} @ {self.unit_price}>"
        )


# ---------------------------------------------------------------------------
# Journal — structured change history for any entity, keyed by (entity_type,
# entity_id). Distinct from LogEntry (a fact about the world, not about a
# specific record) and from Note (durable reference knowledge, not history).
# ---------------------------------------------------------------------------


class Journal(Base):
    __tablename__ = "journal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @classmethod
    def for_entity(cls, session: Session, entity_type: str, entity_id: int) -> Sequence[Journal]:
        return session.scalars(
            select(cls).filter_by(entity_type=entity_type, entity_id=entity_id).order_by(cls.created_at)
        ).all()

    @classmethod
    def record(
        cls,
        session: Session,
        entity_type: str,
        entity_id: int,
        field: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Journal:
        entry = cls(
            entity_type=entity_type,
            entity_id=entity_id,
            field=field,
            old_value=old_value,
            new_value=new_value,
            note=note,
        )
        session.add(entry)
        session.flush()
        return entry

    def __repr__(self) -> str:
        target = f"{self.entity_type}#{self.entity_id}"
        if self.field:
            return f"<Journal {target}.{self.field}>"
        return f"<Journal {target}>"


# ---------------------------------------------------------------------------
# EntityLink
# ---------------------------------------------------------------------------


class EntityLink(Base):
    """Untyped graph edge between any two rows in any mapped table (Goal, Todo, Note, ...),
    addressed the same polymorphic way Journal addresses its target: a type name (the mapped
    class's own __name__, see entity_registry()) plus that row's integer id. There is no
    DB-level FK to either side -- SQLite/Postgres have no construct for "FK to whichever
    table type_a names" -- so referential integrity is enforced once, in create(), by looking
    the id up against entity_registry()[type] before the row is ever written; nothing later (traversal, deletion
    elsewhere in the codebase) re-checks it.

    (type_a, id_a, type_b, id_b, relation) is stored in one canonical order regardless of the
    order create() was called with -- lexicographically smaller (type, id) pair goes in the
    _a columns -- so "the same real-world link" can never be inserted as two structurally
    different rows, and the UniqueConstraint below can actually catch a duplicate.
    """

    __tablename__ = "entity_link"
    __table_args__ = (UniqueConstraint("type_a", "id_a", "type_b", "id_b", "relation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_a: Mapped[str] = mapped_column(String, nullable=False)
    id_a: Mapped[int] = mapped_column(Integer, nullable=False)
    type_b: Mapped[str] = mapped_column(String, nullable=False)
    id_b: Mapped[int] = mapped_column(Integer, nullable=False)
    relation: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @staticmethod
    def entity_registry() -> dict[str, type[Base]]:
        """Every mapped class, live from SQLAlchemy's own declarative registry (shared across
        all Base subclasses) -- not a hand-maintained dict, so a new model in models.py or
        models_pg.py becomes linkable automatically, with nothing here to remember to update."""
        return {m.class_.__name__: m.class_ for m in Base.registry.mappers}

    @classmethod
    def resolve(cls, session: Session, entity_type: str, entity_id: int) -> Any:
        """The row (type, id) actually points at, or None if entity_type is unknown or no such
        row exists -- the one validation this whole table's integrity rests on."""
        model = cls.entity_registry().get(entity_type)
        if model is None:
            return None
        return session.get(model, entity_id)

    @classmethod
    def create(
        cls,
        session: Session,
        type_a: str,
        id_a: int,
        type_b: str,
        id_b: int,
        relation: str,
        note: Optional[str] = None,
    ) -> EntityLink:
        """Validates both endpoints exist (raises ValueError naming the missing side) and
        canonicalizes ordering before insert -- callers never need to pre-sort their own
        arguments, and create(A, B, rel) / create(B, A, rel) always produce the same row."""
        if cls.resolve(session, type_a, id_a) is None:
            raise ValueError(f"{type_a}:{id_a} does not exist")
        if cls.resolve(session, type_b, id_b) is None:
            raise ValueError(f"{type_b}:{id_b} does not exist")
        if (type_b, id_b) < (type_a, id_a):
            type_a, id_a, type_b, id_b = type_b, id_b, type_a, id_a
        link = cls(type_a=type_a, id_a=id_a, type_b=type_b, id_b=id_b, relation=relation, note=note)
        session.add(link)
        session.flush()
        return link

    @classmethod
    def for_entity(cls, session: Session, entity_type: str, entity_id: int) -> Sequence[EntityLink]:
        """Every link touching (entity_type, entity_id) on either side -- the one query both
        `kb link show` traversal and a delete-guard's "what's blocking this" check use."""
        return session.scalars(
            select(cls)
            .where(
                or_(
                    (cls.type_a == entity_type) & (cls.id_a == entity_id),
                    (cls.type_b == entity_type) & (cls.id_b == entity_id),
                )
            )
            .order_by(cls.relation, cls.type_a, cls.id_a, cls.type_b, cls.id_b)
        ).all()

    def other_side(self, entity_type: str, entity_id: int) -> tuple[str, int]:
        """Given one endpoint of this link, the (type, id) of the other endpoint."""
        if (self.type_a, self.id_a) == (entity_type, entity_id):
            return (self.type_b, self.id_b)
        return (self.type_a, self.id_a)

    def __repr__(self) -> str:
        return f"<EntityLink {self.type_a}:{self.id_a} --{self.relation}-- {self.type_b}:{self.id_b}>"


# ---------------------------------------------------------------------------
# Reference
# ---------------------------------------------------------------------------


class Reference(Base):
    __tablename__ = "reference"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # comma-separated
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")

    @classmethod
    def search(cls, session: Session, query: str) -> list[Reference]:
        q = query.lower()
        return [
            r
            for r in session.scalars(select(cls)).all()
            if q in r.title.lower() or (r.tags and q in r.tags.lower()) or (r.notes and q in r.notes.lower())
        ]

    @classmethod
    def create(
        cls,
        session: Session,
        title: str,
        url: Optional[str] = None,
        tags: Optional[str] = None,
        context: Optional[Context] = None,
        notes: Optional[str] = None,
    ) -> Reference:
        ref = cls(title=title, url=url, tags=tags, context_id=context.id if context else None, notes=notes)
        session.add(ref)
        session.flush()
        return ref

    def __repr__(self) -> str:
        return f"<Reference {self.title!r}>"


# ---------------------------------------------------------------------------
# WorkingMemory
# ---------------------------------------------------------------------------


class WorkingMemory(Base):
    __tablename__ = "working_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    domain: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # e.g. "sqlalchemy", "arch-linux"
    body: Mapped[str] = mapped_column(Text, nullable=False)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")

    @classmethod
    def get(cls, session: Session, topic: str) -> Optional[WorkingMemory]:
        return session.scalars(select(cls).filter_by(topic=topic)).one_or_none()

    @classmethod
    def search(cls, session: Session, query: str) -> list[WorkingMemory]:
        q = query.lower()
        return [
            m
            for m in session.scalars(select(cls)).all()
            if q in m.topic.lower() or (m.domain and q in m.domain.lower()) or q in m.body.lower()
        ]

    @classmethod
    def get_or_create(cls, session: Session, topic: str, domain: Optional[str] = None, body: str = "") -> WorkingMemory:
        obj = cls.get(session, topic)
        if obj is None:
            obj = cls(topic=topic, domain=domain, body=body)
            session.add(obj)
            session.flush()
        return obj

    def __repr__(self) -> str:
        domain_str = f" [{self.domain}]" if self.domain else ""
        return f"<WorkingMemory {self.topic!r}{domain_str}>"


# ---------------------------------------------------------------------------
# LogEntry
# ---------------------------------------------------------------------------


class LogEntry(Base, HasEmbedding):
    """A timestamped observation — a fact or set of facts about a moment, not durable reference
    knowledge and not work with a status. Append-only; the point is to build a queryable history
    (health, events, commits referenced by free text) that reveals patterns over time. domain is
    a loose, unenforced label (e.g. "health", "cat", "work") — let structure emerge from actual
    use rather than pre-defining categories."""

    __tablename__ = "log_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"body"}

    def _embed_source_text(self) -> str:
        return self.body

    @classmethod
    def create(
        cls,
        session: Session,
        body: str,
        domain: Optional[str] = None,
        context: Optional[Context] = None,
        occurred_at: Optional[datetime] = None,
    ) -> LogEntry:
        entry = cls(
            body=body, domain=domain, context_id=context.id if context else None, occurred_at=occurred_at or _now()
        )
        entry.reembed()
        session.add(entry)
        session.flush()
        return entry

    @classmethod
    def recent(
        cls, session: Session, domain: Optional[str] = None, context: Optional[Context] = None, limit: int = 20
    ) -> Sequence[LogEntry]:
        q = select(cls).order_by(cls.occurred_at.desc()).limit(limit)
        if domain is not None:
            q = q.where(cls.domain == domain)
        if context is not None:
            q = q.where(cls.context_id == context.id)
        return session.scalars(q).all()

    def __repr__(self) -> str:
        when = self.occurred_at.strftime("%Y-%m-%d")
        body = self.body if len(self.body) <= 60 else self.body[:60] + "…"
        return f"<LogEntry #{self.id} [{when}]{' ' + self.domain if self.domain else ''}: {body!r}>"


# ---------------------------------------------------------------------------
# InboxItem
# ---------------------------------------------------------------------------


class InboxItem(Base):
    """Raw, untriaged capture — the GTD inbox. Unlike everything else in kb, an InboxItem's
    eventual home isn't known at capture time: it might become a Todo, a Purchase, a LogEntry,
    a Note, or get discarded. Triage means deciding what it becomes, then marking triaged_at —
    triage is not a special mechanism, just create the right real record and mark this done."""

    __tablename__ = "inbox_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # capture channel, e.g. "email", "mobile", "quick-note"
    category: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # kind of content, e.g. "project-idea", "purchase"
    triaged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def pending(cls, session: Session, category: Optional[str] = None) -> Sequence[InboxItem]:
        q = select(cls).where(cls.triaged_at.is_(None))
        if category is not None:
            q = q.where(cls.category == category)
        return session.scalars(q.order_by(cls.created_at)).all()

    @classmethod
    def create(
        cls, session: Session, body: str, source: Optional[str] = None, category: Optional[str] = None
    ) -> InboxItem:
        item = cls(body=body, source=source, category=category)
        session.add(item)
        session.flush()
        return item

    def triage(self) -> None:
        self.triaged_at = _now()

    def __repr__(self) -> str:
        state = "triaged" if self.triaged_at else "pending"
        tags = " ".join(f"[{t}]" for t in (self.category, self.source) if t)
        body = self.body if len(self.body) <= 60 else self.body[:60] + "…"
        return f"<InboxItem #{self.id} [{state}]{' ' + tags if tags else ''}: {body!r}>"


class ArchivedLink(Base):
    """A URL queued for archival -- interim capture ahead of a live ArchiveBox instance
    (kb Goal/Todo #70). Today this is just url+title+reason+timestamp; migrated_at marks
    the row as already pushed into a real ArchiveBox once that integration exists, so the
    same table can be replayed against it without re-deciding what's already been sent.
    title and reason are two different axes, both required: title is a neutral description
    of what the page/content actually is (what a fetch against a live ArchiveBox would want
    to auto-fill from the page's own <title>, when a page's own title is generic or missing
    context, override it by hand rather than saving the bare auto-title); reason is why it
    was worth keeping -- what made it pass the filter, what task/question led to finding it.
    Neither is optional -- the point is to never save a bare URL with no record of what it is
    or why it mattered, the same way a link shared with a person should come with why the
    sender thought it mattered rather than dumping the burden of figuring that out on the
    reader later.
    Each row's id is cited elsewhere in kb as ABn (e.g. "AB23") -- embed that token in any
    Note/Todo/Journal body that references the URL, so the pointer travels with the prose
    instead of living only in this table. ABn today means this table's own id; once a live
    ArchiveBox instance exists, migrated ids get remapped to the real AB snapshot id and
    every ABn citation in kb text is updated to match."""

    __tablename__ = "archived_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    migrated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def create(cls, session: Session, url: str, title: str, reason: str) -> ArchivedLink:
        link = cls(url=url, title=title, reason=reason)
        session.add(link)
        session.flush()
        return link

    @classmethod
    def pending(cls, session: Session) -> Sequence[ArchivedLink]:
        return session.scalars(select(cls).where(cls.migrated_at.is_(None)).order_by(cls.created_at)).all()

    def __repr__(self) -> str:
        state = "migrated" if self.migrated_at else "pending"
        return f"<ArchivedLink #{self.id} [{state}] {self.title!r} {self.url}>"


_STORAGE_COLLECTIONS = {c for c in Collection if c != Collection.ALL}


class Note(Base, HasEmbedding):
    """A personal knowledge base / lab notebook entry -- durable facts worth keeping because
    they were useful or interesting to this user, with no claim of being fact-checked, curated,
    or written for an audience. Deliberately NOT designed for shareable/git-tracked export the
    way Instruction is -- see kb Goal #23's Journal for the reasoning (Instruction is reference
    documentation, meant for an audience; Note is a personal notebook, correctness bar is
    "good enough for me")."""

    __tablename__ = "note"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    collection: Mapped[Collection] = mapped_column(
        Enum(Collection, create_constraint=True, validate_strings=True), nullable=False
    )
    tags: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # comma-separated

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "body"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.body}"

    @classmethod
    def create(
        cls, session: Session, title: str, body: str, collection: Collection, tags: Optional[str] = None
    ) -> Note:
        if collection == Collection.ALL:
            raise ValueError("Collection.ALL is a search sentinel and cannot be used for storage.")
        note = cls(title=title, body=body, collection=collection, tags=tags)
        note.reembed()
        session.add(note)
        session.flush()
        return note

    @classmethod
    def get(cls, session: Session, id: int) -> Optional[Note]:
        return session.scalars(select(cls).filter_by(id=id)).one_or_none()

    @classmethod
    def find(cls, session: Session, title: str) -> Optional[Note]:
        return session.scalars(select(cls).filter_by(title=title)).one_or_none()

    def update(self, title: Optional[str] = None, body: Optional[str] = None, tags: Optional[str] = None) -> None:
        if title is not None:
            self.title = title
        if body is not None:
            self.body = body
        if tags is not None:
            self.tags = tags

    def __repr__(self) -> str:
        tags_str = f" #{self.tags}" if self.tags else ""
        return f"<Note {self.collection.value}/{self.title!r}{tags_str}>"


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------


class Wishlist(Base):
    __tablename__ = "wishlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    price_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=50)  # 0–100
    urgency: Mapped[int] = mapped_column(Integer, nullable=False, default=50)  # 0–100
    effort: Mapped[WishlistEffort] = mapped_column(
        Enum(WishlistEffort, create_constraint=True, validate_strings=True), nullable=False, default=WishlistEffort.GRAB
    )
    clarity: Mapped[int] = mapped_column(Integer, nullable=False, default=50)  # 0–100: how well-defined the need is
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0–100: explicit deliberate rank
    status: Mapped[WishlistStatus] = mapped_column(
        Enum(WishlistStatus, create_constraint=True, validate_strings=True),
        nullable=False,
        default=WishlistStatus.ACTIVE,
    )
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # manually marked visible in kb summary

    context: Mapped[Optional[Context]] = relationship("Context")

    @property
    def score(self) -> int:
        return self.importance * self.urgency * self.clarity // 10000

    @classmethod
    def active(cls, session: Session, effort: Optional[WishlistEffort] = None) -> Sequence[Wishlist]:
        q = select(cls).where(cls.status == WishlistStatus.ACTIVE)
        if effort is not None:
            q = q.where(cls.effort == effort)
        return session.scalars(q).all()

    @classmethod
    def top(cls, session: Session, n: int = 10, pinned_only: bool = False) -> list[Wishlist]:
        """Active items: explicit priority first (nulls last), then score as tiebreaker."""
        items = cls.active(session)
        if pinned_only:
            items = [w for w in items if w.pinned]
        return sorted(items, key=lambda w: (w.priority is None, -(w.priority or 0), -w.score))[:n]

    def __repr__(self) -> str:
        price = ""
        if self.price_min is not None or self.price_max is not None:
            lo = f"${self.price_min}" if self.price_min is not None else ""
            hi = f"${self.price_max}" if self.price_max is not None else ""
            price = f" {lo}–{hi}" if lo and hi else f" {lo or hi}"
        priority_str = f" priority={self.priority}" if self.priority is not None else f" score={self.score}"
        pin = " pinned" if self.pinned else ""
        return f"<Wishlist #{self.id} {self.title!r}{price} effort={self.effort.value}{priority_str}{pin}>"


class Idea(Base, HasContextOrTag, HasEmbedding):
    """GTD Someday/Maybe: a project idea you like but haven't committed to acting
    on, distinct from Todo (committed next-action work) and Wishlist (acquire/
    purchase, price-bearing). Deliberately has no defer_until, priority, or score --
    it never resurfaces on its own; you visit it on your own schedule (kb idea list),
    the same way GTD's Someday/Maybe list is only ever seen during a deliberate
    review, never pushed at you. Promotion to a real Goal/Todo/Wishlist is a manual
    relocation (create the new row by hand, record the transition via Journal,
    mark this PROMOTED) -- not a live foreign key, so promoted ideas don't leave a
    permanent cross-reference web behind them."""

    __tablename__ = "idea"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[IdeaStatus] = mapped_column(
        Enum(IdeaStatus, create_constraint=True, validate_strings=True), nullable=False, default=IdeaStatus.ACTIVE
    )
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional[Tag]] = relationship("Tag")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "description", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.description or ''}\n\n{self.notes or ''}"

    @classmethod
    def active(
        cls,
        session: Session,
        context: Optional[Context] = None,
        contexts: Optional[Sequence[Context]] = None,
        include_no_context: bool = False,
    ) -> Sequence[Idea]:
        """`context` matches that single context exactly; `contexts` (e.g. from
        Context.self_and_descendants) matches any context in the given set, plus any
        Idea whose tag_id is carried by a Context in that set (see HasContextOrTag)."""
        q = select(cls).where(cls.status == IdeaStatus.ACTIVE)
        if context is not None:
            q = q.where(cls.context_id == context.id)
        if contexts is not None:
            matches = cls.matches_contexts(contexts)
            q = (
                q.where(matches | (cls.context_id.is_(None) & cls.tag_id.is_(None)))
                if include_no_context
                else q.where(matches)
            )
        return session.scalars(q).all()

    @classmethod
    def create(
        cls,
        session: Session,
        title: str,
        description: Optional[str] = None,
        context: Optional[Context] = None,
        tag: Optional[Tag] = None,
        notes: Optional[str] = None,
    ) -> Idea:
        idea = cls(
            title=title,
            description=description,
            context_id=context.id if context else None,
            tag_id=tag.id if tag else None,
            notes=notes,
        )
        idea.reembed()
        session.add(idea)
        session.flush()
        return idea

    def __repr__(self) -> str:
        return f"<Idea #{self.id} {self.title!r} [{self.status.value}]>"


# ---------------------------------------------------------------------------
# Timer
# ---------------------------------------------------------------------------


class TimerStatus(enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Timer(Base, HasContextOrTag):
    """A DB-backed countdown, distinct from the stateless `timer` CLI -- persisted so a daemon
    process can track and alert on it independently of any running terminal. duration_seconds is
    the total length; ends_at is the single source of truth for when it fires, recomputed whenever
    the timer is (re)started so due-ness is a plain "now >= ends_at" comparison. repeat_count (None
    = run once, 0 = infinite, N = N total runs) mirrors the CLI's -r semantics; completed_runs
    tracks progress through it."""

    __tablename__ = "timer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[TimerStatus] = tracked_column(
        Enum(TimerStatus, create_constraint=True, validate_strings=True), nullable=False, default=TimerStatus.ACTIVE
    )
    repeat_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional[Tag]] = relationship("Tag")

    @classmethod
    def active(
        cls,
        session: Session,
        context: Optional[Context] = None,
        contexts: Optional[Sequence[Context]] = None,
        include_no_context: bool = False,
    ) -> Sequence[Timer]:
        """Same shape as Goal/Todo/Daily/Idea's .active() -- see Todo.active's docstring
        for why every context/tag-addressable entity matches this signature."""
        q = select(cls).where(cls.status == TimerStatus.ACTIVE)
        if context is not None:
            q = q.where(cls.context_id == context.id)
        if contexts is not None:
            matches = cls.matches_contexts(contexts)
            q = (
                q.where(matches | (cls.context_id.is_(None) & cls.tag_id.is_(None)))
                if include_no_context
                else q.where(matches)
            )
        return session.scalars(q).all()

    @classmethod
    def create(
        cls,
        session: Session,
        duration_seconds: int,
        label: Optional[str] = None,
        context: Optional[Context] = None,
        tag: Optional[Tag] = None,
        repeat_count: Optional[int] = None,
    ) -> Timer:
        timer = cls(
            label=label,
            duration_seconds=duration_seconds,
            ends_at=_now() + timedelta(seconds=duration_seconds),
            context_id=context.id if context else None,
            tag_id=tag.id if tag else None,
            repeat_count=repeat_count,
        )
        session.add(timer)
        session.flush()
        return timer

    def cancel(self) -> None:
        self.status = TimerStatus.CANCELLED

    def __repr__(self) -> str:
        label_str = f" {self.label!r}" if self.label else ""
        context_str = f" [{self.context.name}]" if self.context else ""
        tag_str = f" @{self.tag.name}" if self.tag else ""
        return (
            f"<Timer #{self.id}{label_str} [{self.status.value}] "
            f"ends_at={self.ends_at.strftime('%Y-%m-%d %H:%M:%S')}{context_str}{tag_str}>"
        )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create tables for a fresh database. Use alembic for schema changes on existing DBs."""
    Base.metadata.create_all(_engine)
