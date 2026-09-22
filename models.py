"""Personal knowledge base ORM. Single SQLite database at ~/kb/data/kb.db."""

from __future__ import annotations

import enum
import re
import struct
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, Sequence

import psutil
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
    and_,
    create_engine,
    event,
    func,
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
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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
    INBOX = "inbox"  # default collection for a note created without an explicit one

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


class TodoKind(enum.Enum):
    """What kind of work a Todo represents -- Redmine's "Tracker"/Jira's "Issue Type"
    field, orthogonal to TodoStatus (lifecycle) and urgent (priority). BUG marks a
    defect/regression (existing behavior is wrong), distinct from TASK (unfinished
    work with no prior-correct-behavior claim) -- `kb bug` presets this value so a
    bug's kind is never left to default silently."""

    BUG = "bug"
    FEATURE = "feature"
    TASK = "task"
    CHORE = "chore"


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


class TodoSeverity(enum.Enum):
    """How bad it is if this Todo doesn't get done -- impact, orthogonal to `urgent`
    (time-sensitivity: act now regardless of impact). Nullable: most Todos carry no
    meaningful severity, the same reasoning as WishlistEffort being optional."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TodoResolutionDistance(enum.Enum):
    """How many open decisions/unknowns stand between now and this Todo being done --
    epistemic distance to a solution, orthogonal to severity (impact) and effort
    (work size). Matches kb instructions root's own Resolution-Distance Ordering
    exactly, so a punch list sorted by this field sorts the same way that node
    already says to present one by hand. Nullable: most Todos aren't worth this
    assessment, the same reasoning as severity being optional. A freely-settable
    field, not a Definition-of-Ready-style workflow gate -- no mainstream PM tool
    models this as a graduated field (the closest analogs, Cynefin and Agile
    "spikes"/DoR, are all binary workflow states requiring a real triage step), but
    kb has no team-triage-ritual reason to gate it behind one; triage happens
    whenever it happens."""

    MECHANICAL = "mechanical"  # a data fix or config change using an existing mechanism; zero design
    DIAGNOSE = "diagnose"  # likely a small bug, but scope needs confirming before it's mechanical
    CLEAR_SHOT = "clear_shot"  # the design choice is essentially already settled; only implementation remains
    OPEN = "open"  # real design tradeoffs remain; needs discussion before code


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
        """Look up a context by name, raising if it's missing -- used only where the name is
        known-good already (e.g. self_and_descendants walking a Context that was just resolved
        via get_or_create_reporting), never on raw user-typed --context input. See
        get_or_create_reporting for the user-facing path, which creates rather than raises."""
        obj = session.scalars(select(cls).filter_by(name=name)).one_or_none()
        if obj is None:
            raise ValueError(f"no such context: {name!r} (create it with: kb context add {name!r})")
        return obj

    @classmethod
    def get_or_create_reporting(cls, session: Session, name: str) -> tuple[Context, bool]:
        """Look up a context by name, creating a new top-level one if it doesn't exist yet.
        Returns (context, was_created) -- callers print a short "created new context" notice
        when was_created is True (see kb_cli._util.scope_to_context), rather than raising.
        A misspelled --context is meant to be caught by noticing that notice and fixing it
        with `kb context rm`/`context set-parent`, not by a hard error -- a full argparse
        error for a bare typo was expensive to recover from (had to retype a long --body
        verbatim) for a mistake that's actually a 1-2 command fix after the fact."""
        obj = session.scalars(select(cls).filter_by(name=name)).one_or_none()
        if obj is not None:
            return obj, False
        obj = cls(name=name)
        session.add(obj)
        # Commit immediately, independent of whatever the enclosing command later commits
        # (or doesn't) -- a read-only command like `todo list` never calls session.commit(),
        # but the auto-created context must still persist, or the "created" notice would
        # print again on every subsequent call for a context that never actually exists.
        session.commit()
        return obj, True

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
    """A node in the graph of durable guidance -- unifies what would otherwise be scattered
    across CLAUDE.md files, Claude Code skills, and Claude Code memory into one structure. Tree
    structure (topic parent/child, e.g. "engineering" -> "react" -> "dnd-kit") is expressed as
    ordinary EntityLink rows with relation "parent-of" (a --parent-of--> b means a is the parent
    of b), not a parent_id column -- the same graph mechanism every other kb entity already uses
    for cross-references (see EntityLink), so Instruction has one graph mechanism, not two. This
    is a SEPARATE graph from Context's own tree: Context is where something is actionable (e.g.
    "pg" -> "Serbule Hills Tavern"); Instruction's parent-of graph is what topic something belongs
    to, independent of place. A node can optionally also carry a context_id/tag_id (via
    HasContextOrTag) to link it into the Context tree when it's genuinely tied to a place, not
    just a topic (e.g. NPC lore that should surface automatically when Context walks into that
    location). A node may also carry arbitrary non-hierarchical EntityLinks to any other node
    (another Instruction, or a Note/Goal/Todo/etc.) via any other relation label -- roots()/
    children() only ever look at "parent-of" edges, the rest of the graph is free-form.

    trigger is required on every node (enforced by `kb i add`, even a null-DB value on old rows is a
    retrofit gap, not a valid state to create new): it's the short condition shown in a parent's
    children listing that lets an agent decide whether to bother fetching this node's full body at
    all, without reading the body first. A node whose relevance genuinely can't be narrowed still
    gets a trigger -- even a couple words ("engineering work in general") beats none, because an
    unstated trigger is exactly the gap that let nodes go unread: a session skips a child it can't
    yet tell is relevant, and a body-only node gives it nothing to make that call with. There is no
    separate "trigger tree" -- a trigger-worded node's children ARE topic-tree navigation, just
    phrased as conditions ("whenever doing a merge") instead of topic names ("merge").

    Intended navigation is root-to-leaf, one level at a time, judgment-based (which of this level's
    handful of children is obviously relevant), not a search/similarity operation -- keep each node's
    children few enough (~5-10) that this stays cheap; restructure (insert an intermediate node)
    rather than letting any level's fanout grow past that. See kb Goal #23 for full design rationale,
    and kb Todo #127 for the parent_id -> EntityLink graph migration rationale specifically.

    This is the one table meant for shareable, git-trackable export (a design in progress as of
    2026-07 -- see Goal #23) -- unlike Note (a personal notebook), Instruction's content is
    operational reference documentation, genuinely useful to someone else running this system."""

    __tablename__ = "instruction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional["Tag"]] = relationship("Tag")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "body"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.body}"

    _PARENT_RELATION = "parent-of"

    @classmethod
    def roots(cls, session: Session) -> Sequence[Instruction]:
        """Top-level nodes -- no incoming "parent-of" EntityLink -- the entry points to the tree."""
        has_parent_ids = {
            link.id_b
            for link in session.scalars(
                select(EntityLink).where(
                    EntityLink.type_b == "Instruction", EntityLink.relation == cls._PARENT_RELATION
                )
            ).all()
        }
        all_nodes = session.scalars(select(cls)).all()
        return [n for n in all_nodes if n.id not in has_parent_ids]

    @classmethod
    def children(cls, session: Session, parent_id: int) -> Sequence[Instruction]:
        """Direct children of a node (b-side of that node's own "parent-of" EntityLinks), for
        one level of tree expansion."""
        child_ids = [
            link.id_b
            for link in session.scalars(
                select(EntityLink).where(
                    EntityLink.type_a == "Instruction",
                    EntityLink.id_a == parent_id,
                    EntityLink.relation == cls._PARENT_RELATION,
                )
            ).all()
        ]
        if not child_ids:
            return []
        return session.scalars(select(cls).where(cls.id.in_(child_ids))).all()

    @classmethod
    def parent(cls, session: Session, node_id: int) -> Optional[Instruction]:
        """This node's parent, if any -- the a-side of its own incoming "parent-of" EntityLink.
        A node should have at most one; if data ever ends up with more (nothing in the schema
        prevents it, unlike the old parent_id FK), this returns the first and is the one place
        that would need fixing if that invariant is ever enforced more strictly."""
        link = session.scalars(
            select(EntityLink).where(
                EntityLink.type_b == "Instruction",
                EntityLink.id_b == node_id,
                EntityLink.relation == cls._PARENT_RELATION,
            )
        ).first()
        if link is None:
            return None
        return session.get(cls, link.id_a)

    def __repr__(self) -> str:
        trigger_note = f" trigger={self.trigger!r}" if self.trigger else ""
        return f"<Instruction #{self.id} {self.title!r}{trigger_note}{self.age_marker()}>"


class Settings(Base):
    """Single-row table (id=1) for small standalone config values that don't belong on any
    other model. Start here before adding a dedicated settings table for a new value."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_boundary_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notifications_muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notifications_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    archivebox_host: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hard_delete_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

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
        return f"<Person {self.name!r} [{self.tier.value}] closeness={self.closeness}{self.age_marker()}>"


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
# HasAutoLinks
# ---------------------------------------------------------------------------

_ENTITY_REF_RELATION = "mentions"

# Every prose spelling of an entity reference actually in use across kb -- not just the
# TYPE:ID form `kb link add` takes. `kb`'s own CLI output prints bare "#ID" (type implied
# by the command's own context) and prose (including this assistant's own replies) says
# "Note #343"/"Goal #14" as often as "Note:343" -- so all three separators (":", " #", "#")
# are real, existing spellings, not a hypothetical grammar. ArchivedLink is additionally
# referenced as "ABnnn" (no separator, no space) -- its own display prefix, not its class
# name -- established well before this mixin existed (see `kb ab add`'s own printed output),
# so it is special-cased via _ENTITY_REF_ALIASES rather than invented here.
_entity_ref_re = re.compile(r"\b([A-Z][A-Za-z]*)\s?#(\d+)\b|\b([A-Z][A-Za-z]*):(\d+)\b|\bAB(\d+)\b")

# Short display-prefix -> real model (__name__) aliases, for a type spelled by something
# other than its own class name. Checked in resolve/sync_auto_links, not baked into the
# regex groups above, so adding a new alias never means touching the regex again.
_ENTITY_REF_ALIASES = {"AB": "ArchivedLink"}


def _parse_entity_refs(text: str) -> set[tuple[str, int]]:
    """Every TYPE:ID / TYPE #ID / TYPE#ID / ABnnn reference in free text, as (type, id)
    pairs with aliases already resolved (e.g. "AB23" -> ("ArchivedLink", 23)). The one
    place this grammar is parsed -- HasAutoLinks.sync_auto_links is its only caller today,
    but any future reader (a CLI command resolving refs in stored text, a report) should
    call this rather than re-deriving the regex."""
    found: set[tuple[str, int]] = set()
    for type_a, id_a, type_b, id_b, ab_id in _entity_ref_re.findall(text):
        if ab_id:
            found.add(("ArchivedLink", int(ab_id)))
        else:
            entity_type, entity_id = (type_a, id_a) if type_a else (type_b, id_b)
            found.add((_ENTITY_REF_ALIASES.get(entity_type, entity_type), int(entity_id)))
    return found


class HasAutoLinks:
    """Auto-creates EntityLink rows (relation="mentions") for every TYPE:ID reference
    (e.g. "Todo:102") found in a subclass's own free-text fields -- the automatic
    counterpart to `kb link add`, which remains for any relation other than a bare
    mention. Subclasses implement `_link_fields()` (which columns to scan) and get
    auto-linking for free via the before_flush listener below, the same shape
    HasEmbedding uses for auto-reembedding. Only "mentions"-relation links are
    managed here: a manually created link with a different relation touching the
    same pair is left untouched, and a "mentions" link is removed if its source
    token is later edited out of the text (so links don't outlive the reference
    that created them), but a manually-created "mentions" link (if anyone ever adds
    one by hand) is never distinguished from an automatic one, so editing text that
    used to reference it will remove it same as any other -- there is no separate
    "auto" flag on EntityLink itself. EntityLink itself is defined later in this
    file; referenced here only inside method bodies, resolved at call time, not at
    class-definition time, so the forward reference is safe.

    A ref to an unknown type or nonexistent id is silently skipped (not an error) --
    free text is not a validated form, and a typo like "Note:99999" shouldn't block
    a save.

    _link_fields()/_link_source_text() default to whatever HasEmbedding's own
    _embed_fields()/_embed_source_text() already say for a model combining both
    mixins (the common case: the free-text fields worth semantically searching are
    the same ones worth scanning for references) -- a subclass overrides only when
    linking should scan a different field set than embedding does. This is a
    structural default, not a per-model opt-in list: a new HasAutoLinks subclass
    that also has HasEmbedding gets correct behavior with no extra step to
    remember, per kb instructions #15 (brittle-forgettable-defaults) -- the
    original design required every subclass to separately alias these two methods
    to HasEmbedding's, an exclusion-list-shaped gap were a future subclass to omit
    it, since the failure (NotImplementedError) would only surface at first write,
    not at class-definition time."""

    __tablename__: str
    id: Mapped[int]

    def _link_fields(self) -> set[str]:
        if isinstance(self, HasEmbedding):
            return self._embed_fields()
        raise NotImplementedError(f"{type(self).__name__} must override _link_fields()")

    def _link_source_text(self) -> str:
        if isinstance(self, HasEmbedding):
            return self._embed_source_text()
        raise NotImplementedError(f"{type(self).__name__} must override _link_source_text()")

    def sync_auto_links(self, session: Session) -> None:
        entity_type = type(self).__name__
        found = _parse_entity_refs(self._link_source_text())
        # Drop a self-reference -- "Todo:102" appearing in Todo 102's own text isn't a link.
        found.discard((entity_type, self.id))

        existing = {
            (link.other_side(entity_type, self.id), link)
            for link in EntityLink.for_entity(session, entity_type, self.id)
            if link.relation == _ENTITY_REF_RELATION
        }
        existing_refs = {ref for ref, _link in existing}

        for other_type, other_id in found - existing_refs:
            if EntityLink.resolve(session, other_type, other_id) is None:
                continue
            link = EntityLink(
                type_a=entity_type,
                id_a=self.id,
                type_b=other_type,
                id_b=other_id,
                relation=_ENTITY_REF_RELATION,
            )
            session.add(link)

        for ref, link in existing:
            if ref not in found:
                session.delete(link)


_auto_link_candidates: list[Any] = []


@event.listens_for(Session, "before_flush")
def _collect_auto_link_candidates(
    session: Session, flush_context: UOWTransaction, instances: Optional[Sequence[Any]]
) -> None:
    # Collect here (before PKs are necessarily assigned for new rows) but act in
    # after_flush, once every row -- including a brand-new HasAutoLinks instance --
    # has a real primary key. A nested session.flush() from inside before_flush
    # itself raises "Session is already flushing", which is why this can't just
    # flush-then-sync in place the way HasEmbedding's reembed (no PK needed) does.
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, HasAutoLinks):
            state = inspect(obj)
            assert state is not None
            changed = {attr.key for attr in state.attrs if attr.history.has_changes()}
            if obj in session.new or changed & obj._link_fields():
                _auto_link_candidates.append(obj)


@event.listens_for(Session, "after_flush")
def _sync_auto_links_dirty(session: Session, flush_context: UOWTransaction) -> None:
    if not _auto_link_candidates:
        return
    candidates, _auto_link_candidates[:] = list(_auto_link_candidates), []
    for obj in candidates:
        obj.sync_auto_links(session)


# ---------------------------------------------------------------------------
# Goal
# ---------------------------------------------------------------------------


class Goal(Base, HasContextOrTag, HasEmbedding, HasAutoLinks):
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
        q = select(cls).where(cls.status == GoalStatus.ACTIVE, cls.deleted_at.is_(None))
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
        return f"<Goal #{self.id} {self.title!r} [{self.status.value}] {size}b{self.age_marker()}>"


# ---------------------------------------------------------------------------
# Todo
# ---------------------------------------------------------------------------


class Todo(Base, HasContextOrTag, HasEmbedding, HasAutoLinks):
    __tablename__ = "todo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[TodoStatus] = tracked_column(
        Enum(TodoStatus, create_constraint=True, validate_strings=True), nullable=False, default=TodoStatus.PENDING
    )
    kind: Mapped[TodoKind] = mapped_column(
        Enum(TodoKind, create_constraint=True, validate_strings=True), nullable=False, default=TodoKind.TASK
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
    severity: Mapped[Optional[TodoSeverity]] = mapped_column(
        Enum(TodoSeverity, create_constraint=True, validate_strings=True), nullable=True
    )
    resolution_distance: Mapped[Optional[TodoResolutionDistance]] = mapped_column(
        Enum(TodoResolutionDistance, create_constraint=True, validate_strings=True), nullable=True
    )

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
        kind: Optional[TodoKind] = None,
        include_deferred: bool = False,
        severity: Optional[TodoSeverity] = None,
        untriaged: bool = False,
        resolution_distance: Optional[TodoResolutionDistance] = None,
        unscoped_distance: bool = False,
    ) -> Sequence[Todo]:
        """`context` matches that single context exactly; `contexts` (e.g. from
        Context.self_and_descendants) matches any context in the given set, plus any
        Todo whose tag_id is carried by a Context in that set (see HasContextOrTag) --
        use the latter for a context-plus-sub-contexts filter. include_no_context also
        surfaces Todos with no context/tag at all (e.g. for a summary view that treats
        untagged items as always-relevant, regardless of which context is active).
        Named to match Goal/Daily/Idea's own .active() -- every context/tag-addressable
        entity exposes the same shape so a generic renderer can call it uniformly.
        `untriaged` (severity IS NULL) and `severity` (a specific assessed value) are
        mutually exclusive filters on that column; `unscoped_distance`
        (resolution_distance IS NULL) and `resolution_distance` (a specific assessed
        value) are the same pairing for that column -- the caller (kb_cli/todo.py's
        argparse groups) is responsible for not passing both of either pair."""
        q = select(cls).where(cls.status.in_([TodoStatus.PENDING, TodoStatus.IN_PROGRESS]), cls.deleted_at.is_(None))
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
        if kind is not None:
            q = q.where(cls.kind == kind)
        if severity is not None:
            q = q.where(cls.severity == severity)
        if untriaged:
            q = q.where(cls.severity.is_(None))
        if resolution_distance is not None:
            q = q.where(cls.resolution_distance == resolution_distance)
        if unscoped_distance:
            q = q.where(cls.resolution_distance.is_(None))
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
    def recently_completed(
        cls, session: Session, since: datetime, context: Optional[Context] = None, limit: int = 50
    ) -> Sequence[Todo]:
        """DONE Todos updated since the given cutoff, most-recent first -- backs `kb win recent`,
        but also covers a Todo that really was pending first and got completed within the
        window, which is correct: both are "work that got done recently." Not scoped by
        include_deferred/tag fan-out the way active() is, since a completed Todo has no
        remaining defer/pending state to filter on."""
        q = select(cls).where(cls.status == TodoStatus.DONE, cls.updated_at >= since)
        if context is not None:
            q = q.where(cls.context_id == context.id)
        q = q.order_by(cls.updated_at.desc()).limit(limit)
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
        kind: TodoKind = TodoKind.TASK,
        defer_until: Optional[datetime] = None,
        urgent: bool = False,
        severity: Optional[TodoSeverity] = None,
        resolution_distance: Optional[TodoResolutionDistance] = None,
    ) -> Todo:
        todo = cls(
            title=title,
            goal_id=goal.id if goal else None,
            context_id=context.id if context else None,
            tag_id=tag.id if tag else None,
            notes=notes,
            blocked_by_id=blocked_by.id if blocked_by else None,
            effort=effort,
            kind=kind,
            defer_until=defer_until,
            urgent=urgent,
            severity=severity,
            resolution_distance=resolution_distance,
        )
        todo.reembed()
        session.add(todo)
        session.flush()
        return todo

    def __repr__(self) -> str:
        kind_str = f" <{self.kind.value}>" if self.kind != TodoKind.TASK else ""
        effort_str = f" ({self.effort.value})" if self.effort else ""
        defer_str = f" defer_until={self.defer_until.strftime('%Y-%m-%d %H:%M')}" if self.defer_until else ""
        context_str = f" [{self.context.name}]" if self.context else ""
        tag_str = f" @{self.tag.name}" if self.tag else ""
        urgent_str = " !URGENT!" if self.urgent else ""
        severity_str = f" severity={self.severity.value}" if self.severity else ""
        distance_str = f" distance={self.resolution_distance.value}" if self.resolution_distance else ""
        return (
            f"<Todo #{self.id} {self.title!r} [{self.status.value}]{kind_str}{effort_str}{defer_str}"
            f"{context_str}{tag_str}{urgent_str}{severity_str}{distance_str}{self.age_marker()}>"
        )


# ---------------------------------------------------------------------------
# Daily
# ---------------------------------------------------------------------------


class Daily(Base, HasContextOrTag, HasEmbedding):
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

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"description", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.description}\n\n{self.notes}" if self.notes else self.description

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
        q = select(cls).where(cls.is_active.is_(True), cls.deleted_at.is_(None))
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
        q = select(cls).where(cls.is_active.is_(True), cls.deleted_at.is_(None))
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
        daily.reembed()
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

    def catch_up_would_stay_due(self, session: Session) -> bool:
        """Whether this Daily would still be is_due_now() immediately after catch_up() --
        true for a short recurrence (e.g. "daily") landing back on today, or a
        remind_days_before lead-in wide enough to already cover the caught-up date. Computed
        without mutating next_due_date, so the frontend can distinguish a Catch Up that clears
        the row from one that leaves it in place under a different due date."""
        next_due_date = self.next_due_date
        while self._current_day(session, _now()) > next_due_date:
            next_due_date = self._compute_next_due(session, next_due_date)
        today = self._current_day(session, _now())
        window_start = next_due_date - timedelta(days=self.remind_days_before)
        if today < window_start:
            return False
        if self.show_after_hour is not None and today == next_due_date:
            settings = Settings.get(session)
            local_hour = _now().astimezone(settings.resolved_timezone()).hour
            if local_hour < self.show_after_hour:
                return False
        return True

    def __repr__(self) -> str:
        return f"<Daily #{self.id} {self.description!r}{self.age_marker()}>"


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------


class Event(Base, HasContextOrTag, HasEmbedding):
    """A dated occurrence -- distinct from Daily (recurring actionable chore with completion
    state), Todo (committed next-action work), and LogEntry (a fact about the past). An Event
    is a fact pinned to a date/time with no status: a game release, an anniversary, an
    appointment. See kb Idea #13 for the motivating gap (these were previously shoehorned into
    Todo with an ad hoc due-date-like title).

    starts_at is always a full UTC instant (see CLAUDE.md's DateTime(timezone=True) note --
    read it back through _now()-written convention, .replace(tzinfo=utc) before use). is_all_day
    marks a date-only event (an anniversary, a release day) where starts_at's time-of-day
    component is not meaningful -- stored as midnight UTC and never displayed with a clock time,
    rather than adding a separate Date-typed column: one instant column keeps every event
    orderable/comparable the same way, and is_all_day is the one flag that decides whether the
    time-of-day is shown.

    recurrence, when set, is an RFC 5545 RRULE string (e.g. "FREQ=YEARLY;BYMONTH=7;BYMONTHDAY=23"
    for a July 23 anniversary, or "FREQ=WEEKLY;BYDAY=MO,WE,FR" for a 3x/week appointment) --
    expanded via dateutil.rrule.rrulestr(recurrence, dtstart=starts_at), not a hand-rolled
    grammar. Unlike Daily.recurrence (a small, page-sized set of cadences, exempted under kb
    engineering's own "small grammar is fine hand-rolled" rule), an Event's recurrence has no
    fixed small vocabulary -- BYDAY/BYSETPOS/BYMONTH/interval/count/until compose freely, which
    is exactly the shape engineering's root body asks to check against a battle-tested library
    for before hand-rolling. Null recurrence means a one-off event (e.g. a specific game's 1.0
    release date). next_occurrence() is the one place dateutil is invoked, confining the
    dependency to a single thin layer per kb engineering's third-party-library-boundary rule.

    No completion/status field -- an Event isn't actionable work, it's a fact. A recurring
    Event (a birthday) never gets "completed"; only its next_occurrence() moves forward as time
    passes, purely a computed read, never persisted."""

    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurrence: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional[Tag]] = relationship("Tag")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.notes}" if self.notes else self.title

    @classmethod
    def active(
        cls,
        session: Session,
        context: Optional[Context] = None,
        contexts: Optional[Sequence[Context]] = None,
        include_no_context: bool = False,
    ) -> Sequence[Event]:
        """`context` matches that single context exactly; `contexts` (e.g. from
        Context.self_and_descendants) matches any context in the given set, plus any Event
        whose tag_id is carried by a Context in that set (see HasContextOrTag)."""
        q = select(cls).where(cls.deleted_at.is_(None))
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
        starts_at: datetime,
        context: Optional[Context] = None,
        tag: Optional[Tag] = None,
        is_all_day: bool = False,
        recurrence: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Event:
        event_row = cls(
            title=title,
            starts_at=starts_at,
            is_all_day=is_all_day,
            recurrence=recurrence,
            context_id=context.id if context else None,
            tag_id=tag.id if tag else None,
            notes=notes,
        )
        event_row.reembed()
        session.add(event_row)
        session.flush()
        return event_row

    def next_occurrence(self, after: Optional[datetime] = None) -> Optional[datetime]:
        """The next instant this Event lands on, at or after `after` (default: now) -- the
        event's own starts_at itself if it's still upcoming and non-recurring or hasn't started
        recurring yet, otherwise the first RRULE-generated occurrence at or after `after`. None
        once a non-recurring Event's starts_at is fully in the past. The one call site for
        dateutil.rrule in this codebase -- see class docstring."""
        from dateutil.rrule import rrulestr

        after = after or _now()
        starts_at = self.starts_at.replace(tzinfo=timezone.utc) if self.starts_at.tzinfo is None else self.starts_at
        if not self.recurrence:
            return starts_at if starts_at >= after else None
        rule = rrulestr(self.recurrence, dtstart=starts_at)
        occurrence: Optional[datetime] = rule.after(after, inc=True)
        return occurrence

    def occurrences_between(self, range_start: datetime, range_end: datetime) -> list[datetime]:
        """Every instant this Event lands on within [range_start, range_end) -- the
        week/month calendar-grid view's equivalent of next_occurrence's single-instant
        answer. A non-recurring Event contributes at most its own starts_at; a recurring
        one is expanded via dateutil.rrule.rrulestr.between, still the one place this
        class touches dateutil (see class docstring)."""
        from dateutil.rrule import rrulestr

        starts_at = self.starts_at.replace(tzinfo=timezone.utc) if self.starts_at.tzinfo is None else self.starts_at
        if not self.recurrence:
            return [starts_at] if range_start <= starts_at < range_end else []
        rule = rrulestr(self.recurrence, dtstart=starts_at)
        occurrences: list[datetime] = rule.between(range_start, range_end, inc=True)
        return [occ for occ in occurrences if occ < range_end]

    def __repr__(self) -> str:
        return f"<Event #{self.id} {self.title!r}{self.age_marker()}>"


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------


class Item(Base, HasEmbedding):
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

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"name", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.name}\n\n{self.notes}" if self.notes else self.name

    @classmethod
    def by_game(cls, session: Session, game: str) -> Sequence[Item]:
        return session.scalars(select(cls).filter_by(game=game)).all()

    def __repr__(self) -> str:
        return f"<Item #{self.id} {self.name!r} [{self.game}]{self.age_marker()}>"


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


class Vendor(Base, HasEmbedding):
    __tablename__ = "vendor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)  # "irl", "pg", ...
    kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # e.g. "grocery", "npc", "player_shop"
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"name", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.name}\n\n{self.notes}" if self.notes else self.name

    def __repr__(self) -> str:
        return f"<Vendor {self.name!r} [{self.domain}]{self.age_marker()}>"


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


class Purchase(Base, HasEmbedding):
    __tablename__ = "purchase"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("vendor_item.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=1)
    unit_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    total_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    vendor_item: Mapped[VendorItem] = relationship("VendorItem")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"notes"}

    def _embed_source_text(self) -> str:
        item_name = self.vendor_item.item.name if self.vendor_item and self.vendor_item.item else ""
        return f"{item_name}\n\n{self.notes}" if self.notes else item_name

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

    a/b are stored in caller-given order, not canonicalized -- `relation` is a free-text
    label that reads a-to-b (e.g. "tracked-by" means a is tracked by b), so an earlier version
    that sorted (type_a, id_a, type_b, id_b) into one canonical order before insert silently
    flipped the meaning of any asymmetric relation whenever the caller's argument order
    differed from (type, id) sort order -- e.g. create("Note", 98, "Note", 97, "found-during")
    got stored as "Note:97 found-during Note:98", the reverse of what was actually meant. The
    UniqueConstraint below only catches an exact-order duplicate; create(A, B, rel) and
    create(B, A, rel) are treated as two different (probably one of them mistaken) facts, not
    the same fact in two spellings -- deliberately, since there's no way to know a relation is
    symmetric from a plain string.
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
        """Validates both endpoints exist (raises ValueError naming the missing side). Stores
        a/b in exactly the order passed -- relation reads a-to-b, so the caller's order is
        meaningful and is never reordered (see class docstring)."""
        if cls.resolve(session, type_a, id_a) is None:
            raise ValueError(f"{type_a}:{id_a} does not exist")
        if cls.resolve(session, type_b, id_b) is None:
            raise ValueError(f"{type_b}:{id_b} does not exist")
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
        return f"<EntityLink #{self.id} {self.type_a}:{self.id_a} --{self.relation}--> {self.type_b}:{self.id_b}>"


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
        return f"<Reference {self.title!r}{self.age_marker()}>"


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
        return f"<WorkingMemory {self.topic!r}{domain_str}{self.age_marker()}>"


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
    source_ref: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # free-form origin pointer, e.g. a Claude Code session ID -- most entries (a cat note, a
    # health fact) have none; only set when the entry came from a traceable external context

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
        source_ref: Optional[str] = None,
    ) -> LogEntry:
        entry = cls(
            body=body,
            domain=domain,
            context_id=context.id if context else None,
            occurred_at=occurred_at or _now(),
            source_ref=source_ref,
        )
        entry.reembed()
        session.add(entry)
        session.flush()
        return entry

    @classmethod
    def recent(
        cls,
        session: Session,
        domain: Optional[str] = None,
        context: Optional[Context] = None,
        limit: int = 20,
        since: Optional[datetime] = None,
    ) -> Sequence[LogEntry]:
        q = select(cls).order_by(cls.occurred_at.desc()).limit(limit)
        if domain is not None:
            q = q.where(cls.domain == domain)
        if context is not None:
            q = q.where(cls.context_id == context.id)
        if since is not None:
            q = q.where(cls.occurred_at >= since)
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


class ArchivedLinkPushStatus(enum.Enum):
    PENDING = "pending"  # not yet attempted -- fresh row, or startup reconciliation hasn't reached it yet
    QUEUED = "queued"  # background push accepted by the server, not yet resolved
    SUCCESS = "success"  # ab_id confirmed, either via a fresh push or a dedup lookup finding an existing snapshot
    FAILED = "failed"  # push attempted and confirmed failed -- see push_error; only retried via `kb ab retry`


class ArchivedLinkContentStatus(enum.Enum):
    NOT_ATTEMPTED = "not_attempted"  # embedding (if any) covers title+reason only, content never fetched
    EMBEDDED = "embedded"  # content was fetched and folded into the embedding
    FETCH_FAILED = "fetch_failed"  # content fetch was attempted and failed -- see content_fetch_error, `kb ab pull`


class ArchivedLink(Base, HasEmbedding):
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
    every ABn citation in kb text is updated to match.

    push_status tracks the live-ArchiveBox push independently of ab_id/push_error being
    populated, so "is this row still owed attention" is one column, not an inference over two
    others: PENDING (fresh, no push attempted yet) -> QUEUED (kb.service accepted the
    background job) -> SUCCESS or FAILED (resolved, either by a successful push or a dedup
    lookup that found the URL already archived). resolved_at is set only on that final
    transition -- when the row's fate became known, not when a push merely started. A row
    stuck at PENDING/QUEUED across a kb.service restart is exactly what startup reconciliation
    (server.py's lifespan) looks for and logs -- see kb Note #105 and kb Todo #70."""

    __tablename__ = "archived_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    migrated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ab_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    push_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    push_status: Mapped[ArchivedLinkPushStatus] = mapped_column(
        Enum(ArchivedLinkPushStatus, create_constraint=True, validate_strings=True),
        nullable=False,
        default=ArchivedLinkPushStatus.PENDING,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    content_status: Mapped[ArchivedLinkContentStatus] = mapped_column(
        Enum(ArchivedLinkContentStatus, create_constraint=True, validate_strings=True),
        nullable=False,
        default=ArchivedLinkContentStatus.NOT_ATTEMPTED,
    )
    content_fetch_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "reason"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.reason}"

    def reembed_with_content(self, content: str) -> None:
        """The one place content gets folded into the embedding. `content` is a plain function
        argument, never assigned to any attribute (mapped or otherwise) on self, so it never
        reaches the DB and never lingers on the instance -- kb's DB stays limited to
        user-written content plus small derived vectors, never bulk page text (see kb Note
        #162). Deliberately bypasses the base HasEmbedding.reembed()/_embed_source_text() path
        (which takes no arguments and is driven by the before_flush listener off _embed_fields()
        alone) since content-aware embedding is always an explicit, caller-initiated action, not
        something a plain title/reason attribute change should ever trigger. Caller is
        responsible for content_status/content_fetch_error bookkeeping around this call (see
        kb_cli/archivebox.py's fetch_and_embed_content(), the shared function both the
        push-queue worker and `kb ab backfill-content` call)."""
        from embed import embed, model_name

        vec = embed(f"{self.title}\n\n{self.reason}\n\n{content}")
        self.embedding = struct.pack(f"{len(vec)}f", *vec)
        self.embedding_model = model_name()

    @classmethod
    def create(cls, session: Session, url: str, title: str, reason: str) -> ArchivedLink:
        link = cls(url=url, title=title, reason=reason)
        link.reembed()
        session.add(link)
        session.flush()
        return link

    @classmethod
    def needing_content_backfill(cls, session: Session) -> Sequence[ArchivedLink]:
        """SUCCESS-pushed rows whose embedding still only covers title+reason and haven't
        already been recorded as a permanent content-fetch failure -- the exact candidate set
        `kb ab backfill-content` (and the push-queue worker, per-row) operates on. Excluding
        FETCH_FAILED here is what keeps a broken snapshot (e.g. singlefile.html missing) from
        being re-attempted on every single backfill run forever -- `kb ab retry`/`kb ab pull`
        followed by a manual re-embed is the deliberate escape hatch once ArchiveBox actually
        has the content."""
        return session.scalars(
            select(cls)
            .where(cls.push_status == ArchivedLinkPushStatus.SUCCESS)
            .where(cls.content_status == ArchivedLinkContentStatus.NOT_ATTEMPTED)
            .order_by(cls.created_at)
        ).all()

    @classmethod
    def find_by_url(cls, session: Session, url: str) -> Optional[ArchivedLink]:
        return session.scalars(select(cls).where(cls.url == url).order_by(cls.created_at)).first()

    @classmethod
    def pending(cls, session: Session) -> Sequence[ArchivedLink]:
        return session.scalars(select(cls).where(cls.migrated_at.is_(None)).order_by(cls.created_at)).all()

    @classmethod
    def stuck_mid_push(cls, session: Session) -> Sequence[ArchivedLink]:
        """Rows still PENDING/QUEUED -- either never picked up, or mid-flight when kb.service
        last stopped. Startup reconciliation (server.py's lifespan) is the one caller."""
        return session.scalars(
            select(cls)
            .where(cls.push_status.in_((ArchivedLinkPushStatus.PENDING, ArchivedLinkPushStatus.QUEUED)))
            .order_by(cls.created_at)
        ).all()

    def __repr__(self) -> str:
        state = "migrated" if self.migrated_at else "pending"
        return f"<ArchivedLink #{self.id} [{state}] {self.title!r} {self.url}>"


_STORAGE_COLLECTIONS = {c for c in Collection if c != Collection.ALL}


class Note(Base, HasEmbedding, HasAutoLinks):
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
        cls,
        session: Session,
        title: str,
        body: str,
        collection: Collection = Collection.INBOX,
        tags: Optional[str] = None,
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

    def update(
        self,
        title: Optional[str] = None,
        body: Optional[str] = None,
        tags: Optional[str] = None,
        collection: Optional[Collection] = None,
    ) -> None:
        if title is not None:
            self.title = title
        if body is not None:
            self.body = body
        if tags is not None:
            self.tags = tags
        if collection is not None:
            if collection == Collection.ALL:
                raise ValueError("Collection.ALL is a search sentinel and cannot be used for storage.")
            self.collection = collection

    def __repr__(self) -> str:
        tags_str = f" #{self.tags}" if self.tags else ""
        return f"<Note #{self.id} {self.collection.value}/{self.title!r}{tags_str}{self.age_marker()}>"


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
        q = select(cls).where(cls.status == WishlistStatus.ACTIVE, cls.deleted_at.is_(None))
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
        return f"<Wishlist #{self.id} {self.title!r}{price} effort={self.effort.value}{priority_str}{pin}{self.age_marker()}>"


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
        q = select(cls).where(cls.status == IdeaStatus.ACTIVE, cls.deleted_at.is_(None))
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
        return f"<Idea #{self.id} {self.title!r} [{self.status.value}]{self.age_marker()}>"


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
        q = select(cls).where(cls.status == TimerStatus.ACTIVE, cls.deleted_at.is_(None))
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
# HarnessSession + Channel messaging
# ---------------------------------------------------------------------------


class HarnessSessionStatus(enum.Enum):
    INFERRING = "inferring"
    IDLE = "idle"


class HarnessSessionKind(enum.Enum):
    """AGENT (the default) is a real `claude` CLI process, alive/dead by its own pid -- see
    is_alive(). HUMAN is a person participating in Channel messaging from a non-harness
    surface (the web UI's chat view) rather than a Claude Code session; it has no OS process
    of its own, so pid is a meaningless 0 sentinel and is_alive() is unconditionally True for
    this kind -- a human is reachable by definition, not by a liveness check. This is the
    schema-honest alternative to either faking a pid for a human row or loosening
    ChannelMessage.from_session to a nullable FK plus a shadow display-name column: every
    ChannelMessage.from_session still always resolves to a real, addressable HarnessSession
    row, agent or human, with no new nullable column and no unattributable message possible."""

    AGENT = "agent"
    HUMAN = "human"


class HarnessSession(Base):
    """One row per live harness session (a `claude` CLI process, or another harness's
    equivalent), registered at SessionStart and read by `kb sessions` for cross-session
    discovery/messaging -- see Goal #46. Named HarnessSession, not Session, since SQLAlchemy's
    own Session class is already imported under that name throughout this file.

    id is the harness's own session id (harness.py:current_session_id()), not a surrogate --
    it's already globally unique and is exactly what ChannelMessage.from_session and
    ChannelSubscription.session_id need to reference, the same way source_ref (LogEntry) reuses
    it as a plain string rather than inventing a second id space.

    Liveness is a pid check at read time (psutil.pid_exists(pid)) for kind == AGENT, not a
    status flag here -- a crashed/killed process self-heals out of `kb sessions` output with no
    de-registration hook required. Same-machine only for now (pid doesn't resolve across
    hosts); revisit with a last_active_at-based heartbeat instead of/alongside pid if
    cross-machine sessions (SSH, Remote Control) become a real use case -- not designed for
    yet, deliberately. kind == HUMAN skips the pid check entirely -- see HarnessSessionKind.

    status/last_active_at/last_response_at are populated only by hooks that actually observe
    those transitions (UserPromptSubmit -> INFERRING + bump last_active_at, Stop -> IDLE +
    bump last_response_at) -- don't add a field here that no hook can honestly populate.
    is_listening is set/cleared by `kb sessions listen` itself on start and on exit (including
    a SIGTERM trap so a normally-killed listener doesn't leave it stuck true) -- but a SIGKILL,
    an OOM kill, or a harness that reaps the process without ever delivering SIGTERM all skip
    that exit path, and were all confirmed live (2026-08-17, kb Note #163) to leave is_listening
    permanently stuck true with no self-heal. listener_pid (the `kb sessions listen` subprocess's
    own pid, distinct from this row's own `pid` -- the harness process's pid, a different
    process) is what makes that recoverable: is_listening_live() below checks whether
    listener_pid still resolves before trusting the flag, the same pid-liveness pattern this
    class already uses for the row itself (is_alive() below) rather than a status flag with no
    external check."""

    __tablename__ = "harness_session"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cwd: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[HarnessSessionKind] = mapped_column(
        Enum(HarnessSessionKind, create_constraint=True, validate_strings=True),
        nullable=False,
        default=HarnessSessionKind.AGENT,
    )
    status: Mapped[HarnessSessionStatus] = mapped_column(
        Enum(HarnessSessionStatus, create_constraint=True, validate_strings=True),
        nullable=False,
        default=HarnessSessionStatus.IDLE,
    )
    is_listening: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    listener_pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def register(
        cls, session: Session, session_id: str, cwd: str, pid: int, title: Optional[str] = None
    ) -> HarnessSession:
        """Called from a SessionStart hook. Upserts -- a resumed session reuses the same
        harness session id, so this updates cwd/pid/title in place rather than erroring
        on a duplicate PK."""
        existing = session.get(cls, session_id)
        if existing is not None:
            existing.cwd = cwd
            existing.pid = pid
            if title is not None:
                existing.title = title
            session.flush()
            return existing
        row = cls(id=session_id, cwd=cwd, pid=pid, title=title)
        session.add(row)
        session.flush()
        return row

    @classmethod
    def get_or_create_human(cls, session: Session, display_name: str) -> HarnessSession:
        """One HarnessSession row per distinct human display name -- id is a stable
        "human:<display_name>" string (its own id namespace, never collides with a harness's
        own session id) so the same person sending from the web UI under an unchanged display
        name always resolves to the same row rather than growing a new one per message."""
        session_id = f"human:{display_name}"
        existing = session.get(cls, session_id)
        if existing is not None:
            return existing
        row = cls(id=session_id, cwd="", pid=0, title=display_name, kind=HarnessSessionKind.HUMAN)
        session.add(row)
        session.flush()
        return row

    def is_alive(self) -> bool:
        if self.kind == HarnessSessionKind.HUMAN:
            return True
        return psutil.pid_exists(self.pid)

    def is_listening_live(self) -> bool:
        """is_listening, corrected for a listener process that died without clearing its own
        flag (SIGKILL, OOM, a harness reap that skips SIGTERM -- see this class's docstring).
        False whenever the flag is set but listener_pid no longer resolves, so a caller never
        has to trust a self-reported flag with no external check -- the same reasoning that
        already makes is_alive() a pid check instead of a status column."""
        if not self.is_listening:
            return False
        if self.listener_pid is None:
            return False
        return psutil.pid_exists(self.listener_pid)

    @classmethod
    def live(cls, session: Session) -> list[HarnessSession]:
        """Every live AGENT session -- what `kb sessions`/the frontend's Agents page lists.
        Deliberately excludes HUMAN rows even though is_alive() is unconditionally True for
        them: this method answers "which Claude Code sessions can I message/see the status
        of," a different question from "who can post in a Channel" (every messaging query
        that needs to include humans, e.g. Channel membership, goes through HarnessSession
        directly or ChannelSubscription, never through this method)."""
        return [
            row
            for row in session.scalars(select(cls).where(cls.kind == HarnessSessionKind.AGENT)).all()
            if row.is_alive()
        ]

    @classmethod
    def stale_listeners(cls, session: Session) -> list[HarnessSession]:
        """Every row with is_listening stuck True whose listener_pid no longer resolves (see
        is_listening_live()'s docstring for how this happens: SIGKILL/OOM/harness-reap skipping
        the listen loop's own SIGTERM-triggered cleanup). Deliberately not scoped to live() --
        a session itself can be gone (harness closed) while its is_listening flag is still
        stuck true, and that row is exactly as safe to clear as one whose session is alive."""
        return [
            row
            for row in session.scalars(select(cls).where(cls.is_listening.is_(True))).all()
            if not row.is_listening_live()
        ]

    @classmethod
    def clear_stale_listeners(cls, session: Session) -> list[HarnessSession]:
        """DB-only cleanup: clears is_listening/listener_pid on stale_listeners() rows. Never
        touches an OS process -- unlike killing by pid (see kb Note #159's postmortem, 2026-08-17:
        an agent trying to stop its own session's background listener instead killed `kb sessions
        listen` processes for other live sessions by grepping `ps aux`), this only ever corrects
        this row's own bookkeeping for a listener process that has *already* exited on its own.
        A live listener (listener_pid still resolves) is never a candidate, live or not-yours --
        so this is always safe to run broadly, including automatically, with no scoping needed."""
        rows = cls.stale_listeners(session)
        for row in rows:
            row.is_listening = False
            row.listener_pid = None
        return rows

    @classmethod
    def detached_listeners(cls, session: Session) -> list[HarnessSession]:
        """Every row whose listener is genuinely alive (is_listening_live() True) but whose
        own `pid` (the harness process, not listener_pid) has since gone on to register a
        *different*, more recently active HarnessSession row -- a `kb sessions listen` process
        that outlived the specific harness *session* that spawned it, even though the
        underlying OS process (`pid`) is still very much alive.

        Deliberately not `not row.is_alive()` (bare pid liveness) -- confirmed live 2026-08-17
        (kb Note #163's follow-up) that this undercounts: `/clear` resets a Claude Code
        session's transcript and gets issued a brand-new session id (CLAUDE_CODE_SESSION_ID
        is fixed per-process, harness.py:current_session_id() reflects whatever id is current,
        but the *old* id's HarnessSession row and its background `kb sessions listen` task are
        never torn down), all while the OS process backing `pid` keeps right on running under
        the new id. Three real rows were found sharing one pid this way. row.is_alive() reports
        True for all of them, including the two stale ones -- pid liveness alone can't tell
        "this is still my current session" from "this pid moved on to a newer session and I'm
        an abandoned leftover". The real signal is relative: is there another row for the same
        pid with a strictly later last_active_at -- if so, this row's session has been
        superseded and its listener (if still running) is an orphan even though `pid` resolves.

        Distinct from stale_listeners(): that method covers a listener that already died
        without clearing its own flag (DB bookkeeping wrong, no live process to worry about).
        This one is the opposite -- the process is still alive and will poll forever, since
        nothing will ever attach to read its background-task-completion notification again.

        DB-provable, not a `ps aux` grep -- same safety bar clear_stale_listeners() already
        meets (see kb Note #159's postmortem) -- so this is safe to compute broadly, including
        automatically. Unlike clear_stale_listeners() though, correcting this case requires
        actually killing listener_pid, not just fixing the DB row -- see
        kill_detached_listeners()."""
        listening = [
            row
            for row in session.scalars(select(cls).where(cls.is_listening.is_(True))).all()
            if row.is_listening_live()
        ]
        if not listening:
            return []
        pids = {row.pid for row in listening}
        latest_active_by_pid: dict[int, datetime] = {}
        for row in session.scalars(select(cls).where(cls.pid.in_(pids))).all():
            if row.last_active_at is None:
                continue
            current = latest_active_by_pid.get(row.pid)
            if current is None or row.last_active_at > current:
                latest_active_by_pid[row.pid] = row.last_active_at
        return [
            row
            for row in listening
            if row.last_active_at is not None
            and row.pid in latest_active_by_pid
            and row.last_active_at < latest_active_by_pid[row.pid]
        ]

    @classmethod
    def kill_detached_listeners(cls, session: Session) -> list[tuple[HarnessSession, int]]:
        """Terminates (SIGTERM, falling back to SIGKILL if still alive after) every
        detached_listeners() row's listener_pid, then clears is_listening/listener_pid on that
        row -- the actual-process-kill counterpart to clear_stale_listeners()'s DB-only clear.

        Safe to run broadly/automatically for the same reason detached_listeners() is: each
        candidate pid is read from this row's own listener_pid, provably alive (is_listening_live()
        already confirmed it resolves) and provably orphaned (is_alive() confirmed the owning
        harness does not), never guessed from a process-list grep -- so unlike the Note #159
        postmortem this can't collide with another session's live listener.

        Returns (row, killed_pid) pairs rather than bare rows -- row.listener_pid is cleared
        to None as part of this same call, so a caller that wants to report which pid it just
        killed (e.g. cmd_listen's startup sweep) can't read it back off the row afterwards."""
        rows = cls.detached_listeners(session)
        result: list[tuple[HarnessSession, int]] = []
        for row in rows:
            pid = row.listener_pid
            # detached_listeners() only returns rows that passed is_listening_live(), which
            # already requires listener_pid is not None -- assert makes that cross-method
            # invariant explicit and checkable rather than re-widening the type to Optional.
            assert pid is not None, "detached_listeners() row must have a live listener_pid"
            if psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    proc.wait(timeout=2)
                except psutil.TimeoutExpired:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
            result.append((row, pid))
            row.is_listening = False
            row.listener_pid = None
        return result

    def __repr__(self) -> str:
        listening_str = " listening" if self.is_listening else ""
        return f"<HarnessSession {self.id[:8]} [{self.status.value}]{listening_str} cwd={self.cwd!r}>"


class TranscriptCache(Base):
    """Memoizes the per-line-scan result of parsing one Claude Code session transcript
    (~/.claude/projects/*/*.jsonl) -- title, message_count -- keyed by session id (the
    transcript's filename stem, already globally unique per HarnessSession's own docstring).
    Every caller that needs a transcript's derived fields (kb_cli.sessions.list_history_sessions
    for `kb sessions history`/the frontend's past-sessions list, refresh_agent_title for the
    live Agents view) should read through get_or_refresh() rather than opening the file directly,
    so a transcript already scanned once this session/day is never re-parsed for the same
    unchanged content -- these files are append-only during a live session and immutable once
    it ends, but both the live Agents view (polled continuously) and the history view (opened
    repeatedly while browsing) were re-scanning the same bytes on every single read before
    this existed, confirmed live 2026-09-01 as measurably slow on a 20MB/5000-line transcript.

    file_mtime is the dirty check: read via one cheap os.stat() (no file open) on every
    lookup and compared against the stored value -- a real Claude Code transcript is
    append-only while its session is live and untouched once the session ends, so mtime
    strictly increases with new content and never regresses without the file being rewritten
    out from under us (not a real case for these files), making it a sound proxy for content
    change; not a content hash, since a hash still requires reading the whole file, defeating
    the point of caching in the first place. mtime is stored as a DateTime for consistency
    with every other timestamp column in this file, not a Float epoch value which nothing
    else here uses."""

    __tablename__ = "transcript_cache"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    project: Mapped[str] = mapped_column(String, nullable=False)
    file_mtime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    @classmethod
    def get_or_refresh(cls, session: Session, path: Path) -> Optional["TranscriptCache"]:
        """Returns the cached row for `path`'s session id, re-parsing and upserting it first
        if the row is missing or its stored file_mtime doesn't match the file's current
        mtime. None if the transcript is empty/unreadable (nothing worth caching) --
        matches kb_cli.sessions._session_info's own None-on-empty contract, which this
        method wraps rather than replaces (parsing logic has exactly one owner, there;
        imported locally to avoid a models.py <-> kb_cli.sessions import cycle)."""
        from kb_cli.sessions import _session_info

        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        row = session.get(cls, path.stem)
        # row.file_mtime reads back tz-naive (SQLite drops tzinfo on DateTime(timezone=True)
        # columns, see base.py's docstring / AGENTS.md) even though it was always written as
        # UTC via mtime above -- .replace(tzinfo=utc) makes this comparison apples-to-apples;
        # without it every lookup mismatches (naive != aware) and the cache never hits.
        if row is not None and row.file_mtime.replace(tzinfo=timezone.utc) == mtime:
            return row

        info = _session_info(path)
        if info is None:
            if row is not None:
                session.delete(row)
            return None

        if row is None:
            row = cls(session_id=path.stem, project=path.parent.name)
            session.add(row)
        row.project = path.parent.name
        row.file_mtime = mtime
        row.title = info["title"]
        row.message_count = info["message_count"]
        row.updated_at = _now()
        session.flush()
        return row

    def __repr__(self) -> str:
        return f"<TranscriptCache {self.session_id[:8]} {self.message_count} msgs>"


class Channel(Base):
    """The one messaging primitive underneath every shape `kb sessions` exposes -- a DM, the
    broadcast channel, and a future named topic channel (`#synth`, `#kb`) are all just a
    Channel with a different name/membership, not three separate mechanisms. name is None for
    a DM (identity is its two-member subscriber set, found via find_or_create_dm, never a
    name), or a real unique string ("broadcast", "synth", ...) for anything else -- created on
    first subscribe with no separate registration step (IRC's model), see get_or_create_named.
    """

    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)

    @classmethod
    def get_or_create_named(cls, session: Session, name: str) -> Channel:
        existing = session.scalars(select(cls).where(cls.name == name)).first()
        if existing is not None:
            return existing
        row = cls(name=name)
        session.add(row)
        session.flush()
        return row

    @classmethod
    def find_dm(cls, session: Session, a: str, b: str) -> Optional[Channel]:
        """A DM is a nameless Channel whose subscriber set is exactly {a, b} -- found by
        looking for a nameless channel both are subscribed to with no third subscriber, not by
        any stored pairing key, since ChannelSubscription is already the one source of truth
        for membership. Read-only: returns None if no such channel exists yet, the one query
        both find_or_create_dm (below) and a read-only "does this DM exist" caller (e.g. the
        web UI listing channels without creating one just by looking) need to share."""
        candidates = session.scalars(
            select(cls.id)
            .join(ChannelSubscription, ChannelSubscription.channel_id == cls.id)
            .where(cls.name.is_(None), ChannelSubscription.session_id.in_([a, b]))
            .group_by(cls.id)
            .having(func.count(func.distinct(ChannelSubscription.session_id)) == 2)
        ).all()
        for channel_id in candidates:
            total = session.scalar(select(func.count()).where(ChannelSubscription.channel_id == channel_id))
            if total == 2:
                return session.get(cls, channel_id)
        return None

    @classmethod
    def find_or_create_dm(cls, session: Session, a: str, b: str) -> Channel:
        """Creates the channel and subscribes both sessions if find_dm finds none yet."""
        existing = cls.find_dm(session, a, b)
        if existing is not None:
            return existing
        row = cls(name=None)
        session.add(row)
        session.flush()
        ChannelSubscription.subscribe(session, channel_id=row.id, session_id=a)
        ChannelSubscription.subscribe(session, channel_id=row.id, session_id=b)
        return row

    def __repr__(self) -> str:
        return f"<Channel #{self.id} {self.name or '(dm)'}>"


class ChannelSubscription(Base):
    """Live/derived channel membership -- a row here plus HarnessSession.is_alive() is the
    entire definition of "currently in this channel," there is no separate durable roster
    concept. subscribed_at is also the lower bound for how far back a newly-joined session can
    see (a named channel's history before you joined isn't backfilled -- see Channel.unread's
    subscribed_at bound); for a DM both members are subscribed at creation, so that bound is
    moot there but doesn't need special-casing."""

    __tablename__ = "channel_subscription"
    __table_args__ = (UniqueConstraint("channel_id", "session_id", name="uq_channel_subscription"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channel.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("harness_session.id"), nullable=False)
    subscribed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    @classmethod
    def subscribe(cls, session: Session, channel_id: int, session_id: str) -> ChannelSubscription:
        existing = session.scalars(
            select(cls).where(cls.channel_id == channel_id, cls.session_id == session_id)
        ).first()
        if existing is not None:
            return existing
        row = cls(channel_id=channel_id, session_id=session_id)
        session.add(row)
        session.flush()
        return row


class ChannelMessage(Base):
    """One posted message. id is the delivery offset/cursor value (plain autoincrement PK) --
    ChannelRead.up_to_message_id points at one of these directly, no separate sequence needed.
    No to_session field at all, unlike the old SessionMessage: a message belongs to a channel,
    full stop, and who receives it falls out of ChannelSubscription rather than being baked
    into the message row itself -- this is what makes a DM, a broadcast, and a named channel
    the same table."""

    __tablename__ = "channel_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channel.id"), nullable=False)
    from_session: Mapped[str] = mapped_column(String, ForeignKey("harness_session.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    @classmethod
    def post(cls, session: Session, channel_id: int, from_session: str, body: str) -> ChannelMessage:
        msg = cls(channel_id=channel_id, from_session=from_session, body=body)
        session.add(msg)
        session.flush()
        return msg

    @classmethod
    def history(
        cls, session: Session, channel_id: int, before_id: Optional[int] = None, limit: int = 50
    ) -> list[ChannelMessage]:
        """One page of a channel's full message history, newest-first, every sender included
        (unlike unread(), which excludes the caller's own messages and is scoped to what one
        session hasn't read yet) -- backs the web UI's scroll-load-older channel view, where
        "who sent it" is a thing to display, not a thing to filter by. before_id (an id from
        the oldest message already loaded) pages further back; omitted, this is the most
        recent `limit` messages in the channel."""
        q = select(cls).where(cls.channel_id == channel_id)
        if before_id is not None:
            q = q.where(cls.id < before_id)
        rows = session.scalars(q.order_by(cls.id.desc()).limit(limit)).all()
        return list(rows)

    @classmethod
    def unread(cls, session: Session, session_id: str, channel_id: Optional[int] = None) -> Sequence[ChannelMessage]:
        """Messages in channels session_id is subscribed to, with id greater than that
        session's own read cursor for that channel (MAX(up_to_message_id) across its
        ChannelRead rows for the channel, or 0/all if it has never read that channel), bounded
        below by ChannelSubscription.subscribed_at so a session never sees a named channel's
        history from before it joined -- moot for a DM (both members subscribed at creation)
        but applies unconditionally rather than special-casing DMs out of it. channel_id
        narrows to one channel (e.g. cmd_send's own DM); omitted, this is every subscribed
        channel at once (cmd_inbox/cmd_listen's own use)."""
        sub_rows = session.execute(
            select(ChannelSubscription.channel_id, ChannelSubscription.subscribed_at).where(
                ChannelSubscription.session_id == session_id
            )
        ).all()
        subs: list[tuple[int, datetime]] = [(cid, sub_at) for cid, sub_at in sub_rows]
        if channel_id is not None:
            subs = [(cid, sub_at) for cid, sub_at in subs if cid == channel_id]
        if not subs:
            return []
        cursor_rows = session.execute(
            select(ChannelRead.channel_id, func.max(ChannelRead.up_to_message_id))
            .where(ChannelRead.session_id == session_id)
            .group_by(ChannelRead.channel_id)
        ).all()
        cursors: dict[int, int] = {cid: max_id for cid, max_id in cursor_rows}
        clauses = []
        for cid, subscribed_at in subs:
            cursor = cursors.get(cid, 0)
            clauses.append(and_(cls.channel_id == cid, cls.id > cursor, cls.created_at >= subscribed_at))
        return session.scalars(
            select(cls).where(or_(*clauses), cls.from_session != session_id).order_by(cls.created_at)
        ).all()

    def __repr__(self) -> str:
        return f"<ChannelMessage #{self.id} channel={self.channel_id} from={self.from_session}>"


class ChannelRead(Base):
    """One row per read *event* (one `kb sessions inbox`/`listen` call that found unread
    mail), never one row per message -- a session's read cursor for a channel is
    MAX(up_to_message_id) across its own rows here for that channel. Deliberately append-only
    rather than a single upserted cursor: keeps the actual history of when a session checked
    and what it saw as current, so a later consistency check can walk a session's read-event
    sequence per channel and confirm up_to_message_id never skips/lags behind the channel's
    real max message id at that time -- not built yet, but this table's shape is what makes it
    buildable. record() always computes the true current max, never a stale/approximate value,
    which is the one invariant that has to hold for such a check to mean anything."""

    __tablename__ = "channel_read"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channel.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("harness_session.id"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    up_to_message_id: Mapped[int] = mapped_column(Integer, ForeignKey("channel_message.id"), nullable=False)

    @classmethod
    def record(cls, session: Session, channel_id: int, session_id: str) -> Optional[ChannelRead]:
        """Writes one ChannelRead row pinned to the channel's true current max message id.
        Returns None (writes nothing) if the channel has no messages at all yet -- there is no
        meaningful up_to_message_id to record."""
        max_id = session.scalar(select(func.max(ChannelMessage.id)).where(ChannelMessage.channel_id == channel_id))
        if max_id is None:
            return None
        row = cls(channel_id=channel_id, session_id=session_id, up_to_message_id=max_id)
        session.add(row)
        session.flush()
        return row


# ---------------------------------------------------------------------------
# CliInvocation
# ---------------------------------------------------------------------------


class CliInvocation(Base):
    """One record per top-level `kb` CLI invocation -- command text, resolved subcommand
    path, timing, whether it succeeded, the error message if it didn't, and a size-capped
    snapshot of parsed args. Written by the optional `cli_instrumentation` library (a
    private, not-yet-public dependency -- see the `kb` script's own ImportError fallback
    and kb_cli/stats.py) via the `kb` script's own entry point, independent of any one
    subcommand knowing about it, so every invocation is covered without each kb_cli/*.py
    module having to opt in. Without cli_instrumentation installed, this table simply stays
    empty -- nothing else in kb depends on it being populated. The point is to make CLI
    friction (a confusing error, a command that fails the same way repeatedly) and CLI usage
    patterns (unused commands, commonly used flags) queryable (`kb stats`) instead of relying
    on friction being reported by hand each time it's hit -- see kb Instruction root, "the
    tree's own re-check mechanisms... exist for exactly this: surfacing friction proactively,
    not after the fact," applied to the CLI's own errors and usage.

    `args_json` stores cli_instrumentation's already-truncated args snapshot verbatim, as a
    single JSON column rather than normalized per-arg columns/rows -- its shape varies by
    subcommand and is expected to change as instrumentation needs evolve, and decomposing it
    is a decision to make later, driven by an actual query or storage-size need that shows up
    in practice, not up front."""

    __tablename__ = "cli_invocation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    subcommand: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    args_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        status = "ok" if self.success else "error"
        return f"<CliInvocation #{self.id} [{status}] {self.command!r}>"


class UsageSample(Base):
    """A single point-in-time reading of `claude -p /usage`'s session/week percentages,
    recorded by `kb_cli.usage.fetch_usage()` each time it performs a real (non-cached) fetch --
    never on a cache hit, so samples are naturally throttled to at most 1/minute by
    `_CACHE_MAX_AGE` regardless of how many CLI/web callers ask in that window. The point is an
    over-time record (`kb stats usage --history`, future charts) that can answer "was that spike
    10 minutes or 2 hours" after the fact, not just show the current instantaneous reading.
    `raw_text` samples (no usage yet) are not recorded -- there is nothing numeric to chart."""

    __tablename__ = "usage_sample"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    session_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    session_resets_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    week_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    week_resets_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<UsageSample #{self.id} session={self.session_pct}% week={self.week_pct}%>"


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create tables for a fresh database. Use alembic for schema changes on existing DBs."""
    Base.metadata.create_all(_engine)
