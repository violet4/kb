"""Personal knowledge base ORM. Single SQLite database at ~/kb/data/kb.db."""
from __future__ import annotations

import enum
import struct
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

import sqlite_vec
from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text,
    create_engine, event, inspect, select,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, MappedColumn, mapped_column, object_session,
    relationship, scoped_session, sessionmaker,
)
from sqlalchemy.orm.attributes import NO_VALUE, NEVER_SET

_DB_PATH = Path(__file__).parent / "data" / "kb.db"
_engine = create_engine(f"sqlite:///{_DB_PATH}", echo=False)


@event.listens_for(_engine, "connect")
def _set_pragma(conn, _):
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")


_Session = scoped_session(sessionmaker(bind=_engine))
sess = _Session()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


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


def tracked_column(*args, **kwargs) -> MappedColumn:
    """Drop-in for mapped_column that records changes to ChangeLog on assignment."""
    col = mapped_column(*args, **kwargs)
    col.column.info["tracked"] = True
    return col


def _on_tracked_set(target, value, oldvalue, initiator):
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


def _register_tracked_listeners(mapper, cls):
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


class WishlistEffort(enum.Enum):
    GRAB = "grab"        # next time you're out
    RESEARCH = "research"  # needs investigation before buying
    PROJECT = "project"  # multi-step effort (e.g. server upgrade)


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

class Context(Base):
    __tablename__ = "context"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @classmethod
    def get_or_create(cls, name: str, description: Optional[str] = None) -> Context:
        obj = sess.scalars(select(cls).filter_by(name=name)).one_or_none()
        if obj is None:
            obj = cls(name=name, description=description)
            sess.add(obj)
            sess.flush()
        return obj

    def __repr__(self) -> str:
        return f"<Context {self.name!r}>"


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------

class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[PersonTier] = mapped_column(Enum(PersonTier, create_constraint=True, validate_strings=True), nullable=False, default=PersonTier.ACQUAINTANCE)
    closeness: Mapped[int] = tracked_column(Integer, nullable=False, default=0)
    last_contacted: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reach_out_every_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @classmethod
    def get(cls, name: str) -> Optional[Person]:
        return sess.scalars(select(cls).filter_by(name=name)).one_or_none()

    @classmethod
    def get_or_create(cls, name: str, tier: PersonTier = PersonTier.ACQUAINTANCE) -> Person:
        obj = cls.get(name)
        if obj is None:
            obj = cls(name=name, tier=tier)
            sess.add(obj)
            sess.flush()
        return obj

    @classmethod
    def in_my_life(cls) -> list[Person]:
        """People who are part of my immediate surrounding life (excludes public figures)."""
        return sess.scalars(
            select(cls).where(cls.tier != PersonTier.PUBLIC_FIGURE).order_by(cls.closeness.desc())
        ).all()

    @classmethod
    def overdue_for_contact(cls) -> list[Person]:
        """People I should have reached out to by now, ordered by most overdue."""
        now = _now()
        candidates = sess.scalars(
            select(cls)
            .where(cls.tier != PersonTier.PUBLIC_FIGURE)
            .where(cls.reach_out_every_days.isnot(None))
        ).all()
        overdue = []
        for p in candidates:
            if p.last_contacted is None:
                overdue.append((p, None))
            else:
                last = p.last_contacted.replace(tzinfo=timezone.utc) if p.last_contacted.tzinfo is None else p.last_contacted
                days_since = (now - last).days
                if days_since >= p.reach_out_every_days:
                    overdue.append((p, days_since))
        overdue.sort(key=lambda x: (x[1] is None, -(x[1] or 0)))
        return [p for p, _ in overdue]

    def __repr__(self) -> str:
        return f"<Person {self.name!r} [{self.tier.value}] closeness={self.closeness}>"


# ---------------------------------------------------------------------------
# Goal
# ---------------------------------------------------------------------------

class Goal(Base):
    __tablename__ = "goal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[GoalStatus] = tracked_column(Enum(GoalStatus, create_constraint=True, validate_strings=True), nullable=False, default=GoalStatus.ACTIVE)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")
    todos: Mapped[list[Todo]] = relationship("Todo", back_populates="goal")

    @classmethod
    def active(cls, context: Optional[Context] = None) -> list[Goal]:
        q = select(cls).where(cls.status == GoalStatus.ACTIVE)
        if context is not None:
            q = q.where(cls.context_id == context.id)
        return sess.scalars(q).all()

    @classmethod
    def create(cls, title: str, description: Optional[str] = None, context: Optional[Context] = None, notes: Optional[str] = None) -> Goal:
        goal = cls(title=title, description=description, context_id=context.id if context else None, notes=notes)
        sess.add(goal)
        sess.flush()
        return goal

    def __repr__(self) -> str:
        return f"<Goal {self.title!r} [{self.status.value}]>"


# ---------------------------------------------------------------------------
# Todo
# ---------------------------------------------------------------------------

class Todo(Base):
    __tablename__ = "todo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[TodoStatus] = tracked_column(Enum(TodoStatus, create_constraint=True, validate_strings=True), nullable=False, default=TodoStatus.PENDING)
    goal_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("goal.id"), nullable=True)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    goal: Mapped[Optional[Goal]] = relationship("Goal", back_populates="todos")
    context: Mapped[Optional[Context]] = relationship("Context")

    @classmethod
    def pending(cls, context: Optional[Context] = None) -> list[Todo]:
        q = select(cls).where(cls.status.in_([TodoStatus.PENDING, TodoStatus.IN_PROGRESS]))
        if context is not None:
            q = q.where(cls.context_id == context.id)
        return sess.scalars(q).all()

    @classmethod
    def create(cls, title: str, goal: Optional[Goal] = None, context: Optional[Context] = None, notes: Optional[str] = None) -> Todo:
        todo = cls(title=title, goal_id=goal.id if goal else None, context_id=context.id if context else None, notes=notes)
        sess.add(todo)
        sess.flush()
        return todo

    def __repr__(self) -> str:
        return f"<Todo {self.title!r} [{self.status.value}]>"


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
    def search(cls, query: str) -> list[Reference]:
        q = query.lower()
        return [
            r for r in sess.scalars(select(cls)).all()
            if q in r.title.lower()
            or (r.tags and q in r.tags.lower())
            or (r.notes and q in r.notes.lower())
        ]

    @classmethod
    def create(cls, title: str, url: Optional[str] = None, tags: Optional[str] = None, context: Optional[Context] = None, notes: Optional[str] = None) -> Reference:
        ref = cls(title=title, url=url, tags=tags, context_id=context.id if context else None, notes=notes)
        sess.add(ref)
        sess.flush()
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
    def get(cls, topic: str) -> Optional[WorkingMemory]:
        return sess.scalars(select(cls).filter_by(topic=topic)).one_or_none()

    @classmethod
    def search(cls, query: str) -> list[WorkingMemory]:
        q = query.lower()
        return [
            m for m in sess.scalars(select(cls)).all()
            if q in m.topic.lower()
            or (m.domain and q in m.domain.lower())
            or q in m.body.lower()
        ]

    @classmethod
    def get_or_create(cls, topic: str, domain: Optional[str] = None, body: str = "") -> WorkingMemory:
        obj = cls.get(topic)
        if obj is None:
            obj = cls(topic=topic, domain=domain, body=body)
            sess.add(obj)
            sess.flush()
        return obj

    def __repr__(self) -> str:
        domain_str = f" [{self.domain}]" if self.domain else ""
        return f"<WorkingMemory {self.topic!r}{domain_str}>"


# ---------------------------------------------------------------------------
# Note (RAG)
# ---------------------------------------------------------------------------

_STORAGE_COLLECTIONS = {c for c in Collection if c != Collection.ALL}


def _embed_text(title: str, body: str) -> bytes:
    from embed import embed
    vec = embed(f"{title}\n\n{body}")
    return struct.pack(f"{len(vec)}f", *vec)


class Note(Base):
    __tablename__ = "note"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    collection: Mapped[Collection] = mapped_column(Enum(Collection, create_constraint=True, validate_strings=True), nullable=False)
    tags: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # comma-separated
    embedding_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    embedding: Mapped[Optional[bytes]] = mapped_column(Text, nullable=True)

    @classmethod
    def create(cls, title: str, body: str, collection: Collection, tags: Optional[str] = None) -> Note:
        if collection == Collection.ALL:
            raise ValueError("Collection.ALL is a search sentinel and cannot be used for storage.")
        from embed import model_name
        note = cls(title=title, body=body, collection=collection, tags=tags)
        note.embedding = _embed_text(title, body)
        note.embedding_model = model_name()
        sess.add(note)
        sess.flush()
        return note

    @classmethod
    def get(cls, id: int) -> Optional[Note]:
        return sess.scalars(select(cls).filter_by(id=id)).one_or_none()

    @classmethod
    def find(cls, title: str) -> Optional[Note]:
        return sess.scalars(select(cls).filter_by(title=title)).one_or_none()

    def update(self, title: Optional[str] = None, body: Optional[str] = None, tags: Optional[str] = None) -> None:
        if title is not None:
            self.title = title
        if body is not None:
            self.body = body
        if tags is not None:
            self.tags = tags
        if title is not None or body is not None:
            self.reembed()

    @classmethod
    def search(cls, query: str, collection: Collection) -> list[tuple[Note, float]]:
        from embed import embed, model_name
        raw = embed(query)
        vec = struct.pack(f"{len(raw)}f", *raw)
        mn = model_name()
        if collection == Collection.ALL:
            sql = "SELECT id, vec_distance_cosine(embedding, ?) AS dist FROM note WHERE embedding_model = ? ORDER BY dist ASC LIMIT 10"
            params = (vec, mn)
        else:
            sql = "SELECT id, vec_distance_cosine(embedding, ?) AS dist FROM note WHERE embedding_model = ? AND collection = ? ORDER BY dist ASC LIMIT 10"
            params = (vec, mn, collection.name)
        with _engine.connect() as conn:
            rows = conn.connection.execute(sql, params).fetchall()
        notes = {n.id: n for n in sess.scalars(select(cls).where(cls.id.in_([r[0] for r in rows]))).all()}
        return [(notes[r[0]], r[1]) for r in rows if r[0] in notes]

    def reembed(self) -> None:
        from embed import model_name
        self.embedding = _embed_text(self.title, self.body)
        self.embedding_model = model_name()

    def __repr__(self) -> str:
        tags_str = f" #{self.tags}" if self.tags else ""
        return f"<Note {self.collection.value}/{self.title!r}{tags_str}>"


@event.listens_for(sess, "before_flush")
def _reembed_dirty_notes(session, flush_context, instances):
    for obj in session.dirty:
        if isinstance(obj, Note):
            changed = {attr.key for attr in inspect(obj).attrs if attr.history.has_changes()}
            if "title" in changed or "body" in changed:
                obj.reembed()


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
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=50)      # 0–100
    urgency: Mapped[int] = mapped_column(Integer, nullable=False, default=50)         # 0–100
    effort: Mapped[WishlistEffort] = mapped_column(Enum(WishlistEffort, create_constraint=True, validate_strings=True), nullable=False, default=WishlistEffort.GRAB)
    clarity: Mapped[int] = mapped_column(Integer, nullable=False, default=50)         # 0–100: how well-defined the need is
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)           # 0–100: explicit deliberate rank
    status: Mapped[WishlistStatus] = mapped_column(Enum(WishlistStatus, create_constraint=True, validate_strings=True), nullable=False, default=WishlistStatus.ACTIVE)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")

    @property
    def score(self) -> int:
        return self.importance * self.urgency * self.clarity // 10000

    @classmethod
    def active(cls, effort: Optional[WishlistEffort] = None) -> list[Wishlist]:
        q = select(cls).where(cls.status == WishlistStatus.ACTIVE)
        if effort is not None:
            q = q.where(cls.effort == effort)
        return sess.scalars(q).all()

    @classmethod
    def top(cls, n: int = 10) -> list[Wishlist]:
        """Active items: explicit priority first (nulls last), then score as tiebreaker."""
        items = cls.active()
        return sorted(items, key=lambda w: (w.priority is None, -(w.priority or 0), -w.score))[:n]

    def __repr__(self) -> str:
        price = ""
        if self.price_min is not None or self.price_max is not None:
            lo = f"${self.price_min}" if self.price_min is not None else ""
            hi = f"${self.price_max}" if self.price_max is not None else ""
            price = f" {lo}–{hi}" if lo and hi else f" {lo or hi}"
        priority_str = f" priority={self.priority}" if self.priority is not None else f" score={self.score}"
        return f"<Wishlist {self.title!r}{price} effort={self.effort.value}{priority_str}>"


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables for a fresh database. Use alembic for schema changes on existing DBs."""
    Base.metadata.create_all(_engine)
