"""Personal knowledge base ORM. Single SQLite database at ~/kb/data/kb.db."""
from __future__ import annotations

import enum
import struct
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from pathlib import Path
from typing import Optional

import sqlite_vec
from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
    create_engine, event, inspect, select,
)
from sqlalchemy.orm import (
    Mapped, MappedColumn, mapped_column, object_session,
    relationship, scoped_session, sessionmaker,
)
from sqlalchemy.orm.attributes import NO_VALUE, NEVER_SET

from base import Base, _now
from mixins import HasWeight

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


class DailyTier(enum.Enum):
    CRITICAL = "critical"   # always surfaces in summary until completed today
    OPTIONAL = "optional"   # hidden by default, needs an explicit request (e.g. kb daily list --all)


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


class CurrentContext(Base):
    """Single-row table: which Context is active by default. See context.py for resolution logic."""
    __tablename__ = "current_context"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")

    @classmethod
    def get(cls) -> Optional[Context]:
        row = sess.scalars(select(cls).filter_by(id=1)).one_or_none()
        return row.context if row else None

    @classmethod
    def set(cls, context: Optional[Context]) -> None:
        row = sess.scalars(select(cls).filter_by(id=1)).one_or_none()
        if row is None:
            row = cls(id=1, context_id=context.id if context else None)
            sess.add(row)
        else:
            row.context_id = context.id if context else None
        sess.flush()

    def __repr__(self) -> str:
        return f"<CurrentContext {self.context.name if self.context else None!r}>"


class Settings(Base):
    """Single-row table (id=1) for small standalone config values that don't belong on any
    other model. Start here before adding a dedicated settings table for a new value."""
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_boundary_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    @classmethod
    def get(cls) -> Settings:
        row = sess.scalars(select(cls).filter_by(id=1)).one_or_none()
        if row is None:
            row = cls(id=1)
            sess.add(row)
            sess.flush()
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
        size = len(self.title) + len(self.description or "") + len(self.notes or "")
        return f"<Goal #{self.id} {self.title!r} [{self.status.value}] {size}b>"


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
    blocked_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("todo.id"), nullable=True)
    effort: Mapped[Optional[WishlistEffort]] = mapped_column(Enum(WishlistEffort, create_constraint=True, validate_strings=True), nullable=True)
    defer_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    goal: Mapped[Optional[Goal]] = relationship("Goal", back_populates="todos")
    context: Mapped[Optional[Context]] = relationship("Context")
    blocked_by: Mapped[Optional[Todo]] = relationship("Todo", remote_side=[id])
    tags: Mapped[list["TodoTag"]] = relationship("TodoTag", secondary="todo_tag_link")

    @classmethod
    def pending(cls, context: Optional[Context] = None, effort: Optional[WishlistEffort] = None,
                include_deferred: bool = False, tag: Optional["TodoTag"] = None) -> list[Todo]:
        q = select(cls).where(cls.status.in_([TodoStatus.PENDING, TodoStatus.IN_PROGRESS]))
        if context is not None:
            q = q.where(cls.context_id == context.id)
        if effort is not None:
            q = q.where(cls.effort == effort)
        if not include_deferred:
            q = q.where((cls.defer_until.is_(None)) | (cls.defer_until <= _now()))
        todos = sess.scalars(q).all()
        if tag is not None:
            # Match if the Todo carries `tag` itself, or any tag whose ancestor chain includes it
            # (e.g. filtering by "grocery" also matches a Todo tagged only "winco").
            todos = [t for t in todos if any(tag in tg.ancestors() for tg in t.tags)]
        return todos

    @classmethod
    def create(cls, title: str, goal: Optional[Goal] = None, context: Optional[Context] = None,
               notes: Optional[str] = None, blocked_by: Optional[Todo] = None,
               effort: Optional[WishlistEffort] = None, defer_until: Optional[datetime] = None) -> Todo:
        todo = cls(title=title, goal_id=goal.id if goal else None, context_id=context.id if context else None,
                   notes=notes, blocked_by_id=blocked_by.id if blocked_by else None, effort=effort,
                   defer_until=defer_until)
        sess.add(todo)
        sess.flush()
        return todo

    def __repr__(self) -> str:
        effort_str = f" ({self.effort.value})" if self.effort else ""
        defer_str = f" defer_until={self.defer_until.strftime('%Y-%m-%d %H:%M')}" if self.defer_until else ""
        context_str = f" [{self.context.name}]" if self.context else ""
        tags_str = f" @{','.join(t.name for t in self.tags)}" if self.tags else ""
        return f"<Todo #{self.id} {self.title!r} [{self.status.value}]{effort_str}{defer_str}{context_str}{tags_str}>"


class TodoTag(Base):
    """A GTD-style actionability tag (e.g. 'serbule-keep', 'has-carrots') -- distinct from Context
    (which game/character), this is many-to-many: a Todo surfaces when any of its tags currently
    applies (you're at that location, you're holding that item, etc).

    parent_id forms a tag hierarchy (adjacency list) -- e.g. 'winco' has parent 'grocery', so a
    Todo tagged only 'winco' still surfaces when filtering by the broader 'grocery' tag, without
    needing to be tagged with both. Standard taxonomy-tree pattern, same shape as folder trees or
    category trees; matches this project's own hierarchy-over-flat-lists principle."""
    __tablename__ = "todo_tag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("todo_tag.id"), nullable=True)

    parent: Mapped[Optional[TodoTag]] = relationship("TodoTag", remote_side=[id])

    def ancestors(self) -> list[TodoTag]:
        """This tag plus every parent up the chain, broadest last."""
        chain = [self]
        node = self
        while node.parent is not None:
            node = node.parent
            chain.append(node)
        return chain

    def __repr__(self) -> str:
        parent_str = f" -> {self.parent.name}" if self.parent else ""
        return f"<TodoTag {self.name!r}{parent_str}>"


class TodoTagLink(Base):
    __tablename__ = "todo_tag_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    todo_id: Mapped[int] = mapped_column(Integer, ForeignKey("todo.id"), nullable=False)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("todo_tag.id"), nullable=False)


# ---------------------------------------------------------------------------
# Daily
# ---------------------------------------------------------------------------

class Daily(Base):
    """A recurring/optional item — distinct from Goal (a purpose/end-state) and Todo (a step toward one).

    domain ("irl"/"pg", mirrors Vendor.domain) separates life-maintenance dailies from game dailies.
    tier controls default summary visibility: CRITICAL always surfaces until completed today,
    OPTIONAL stays hidden unless explicitly requested. last_completed_at + Settings.day_boundary_hour
    is what "completed today" is checked against, so a late bedtime doesn't immediately re-surface
    the next day's dailies at literal midnight.

    recurrence is an optional cadence rule (grammar below); when set, completing the Daily computes
    and stores next_due_at once, so `due()` lookups are a cheap timestamp comparison rather than
    recomputing cadence math on every read. When recurrence is unset, `due()` falls back to the
    plain day-boundary check (last_completed_at vs. the current day-window).

    Recurrence grammar:
      "daily"        -- due again at the next day-boundary after completion (equivalent to unset).
      "every:N"      -- due again N days after completion (e.g. "every:2" for alternating-day items).
      "weekly:DAY"   -- due again on the next occurrence of DAY ("MON".."SUN") after completion.
      "monthly:D"    -- due again on day D of the next applicable month after completion (D 1-28).
    """
    __tablename__ = "daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    domain: Mapped[str] = mapped_column(String, nullable=False, default="irl")
    tier: Mapped[DailyTier] = mapped_column(Enum(DailyTier, create_constraint=True, validate_strings=True), nullable=False, default=DailyTier.CRITICAL)
    recurrence: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reward: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")

    _WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

    @classmethod
    def _day_start(cls, now: datetime) -> datetime:
        """The start of the current day-window, in UTC -- computed by applying
        Settings.day_boundary_hour in local time (not UTC), so a late local bedtime
        doesn't get treated as already past a UTC-midnight-adjacent cutoff."""
        settings = Settings.get()
        local_now = now.astimezone(settings.resolved_timezone())
        local_day_start = local_now.replace(hour=settings.day_boundary_hour, minute=0, second=0, microsecond=0)
        if local_now < local_day_start:
            local_day_start -= timedelta(days=1)
        return local_day_start.astimezone(timezone.utc)

    @classmethod
    def active(cls, context: Optional[Context] = None) -> list[Daily]:
        q = select(cls).where(cls.is_active.is_(True))
        if context is not None:
            q = q.where(cls.context_id == context.id)
        return sess.scalars(q).all()

    @classmethod
    def due(cls, domain: Optional[str] = None, tier: Optional[DailyTier] = None) -> list[Daily]:
        """Active dailies currently due: dailies with a recurrence rule are due once next_due_at
        has passed; dailies without one fall back to the plain day-boundary check against
        last_completed_at."""
        now = _now()
        day_start = cls._day_start(now)
        q = select(cls).where(cls.is_active.is_(True))
        if domain is not None:
            q = q.where(cls.domain == domain)
        if tier is not None:
            q = q.where(cls.tier == tier)
        dailies = sess.scalars(q).all()

        def _aware(dt):
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

        result = []
        for d in dailies:
            if d.recurrence is not None:
                if d.next_due_at is None or _aware(d.next_due_at) <= now:
                    result.append(d)
            elif d.last_completed_at is None or _aware(d.last_completed_at) < day_start:
                result.append(d)
        return result

    @classmethod
    def create(cls, description: str, context: Optional[Context] = None, domain: str = "irl",
               tier: DailyTier = DailyTier.CRITICAL, recurrence: Optional[str] = None,
               location: Optional[str] = None, reward: Optional[str] = None,
               notes: Optional[str] = None) -> Daily:
        daily = cls(description=description, context_id=context.id if context else None,
                    domain=domain, tier=tier, recurrence=recurrence, location=location,
                    reward=reward, notes=notes)
        sess.add(daily)
        sess.flush()
        return daily

    def _compute_next_due(self, after: datetime) -> datetime:
        """The next due timestamp (UTC) per this Daily's recurrence rule, computed in local time
        so weekly/monthly targets land on the intended local calendar day."""
        settings = Settings.get()
        tz = settings.resolved_timezone()
        local_after = after.astimezone(tz)
        kind, _, arg = self.recurrence.partition(":")

        if kind == "daily" or not kind:
            local_next = local_after
        elif kind == "every":
            local_next = local_after + timedelta(days=int(arg))
        elif kind == "weekly":
            target = Daily._WEEKDAYS.index(arg.upper())
            days_ahead = (target - local_after.weekday()) % 7
            days_ahead = days_ahead or 7
            local_next = local_after + timedelta(days=days_ahead)
        elif kind == "monthly":
            day = int(arg)
            year, month = local_after.year, local_after.month + 1
            if month > 12:
                month = 1
                year += 1
            local_next = local_after.replace(year=year, month=month, day=day)
        else:
            raise ValueError(f"unknown recurrence kind: {kind!r}")

        local_next = local_next.replace(hour=settings.day_boundary_hour, minute=0, second=0, microsecond=0)
        return local_next.astimezone(timezone.utc)

    def complete(self) -> None:
        now = _now()
        self.last_completed_at = now
        if self.recurrence is not None:
            self.next_due_at = self._compute_next_due(now)

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
    def by_game(cls, game: str) -> list[Item]:
        return sess.scalars(select(cls).filter_by(game=game)).all()

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
        return f"<Purchase {self.quantity}x {self.vendor_item.item.name if self.vendor_item else '?'} @ {self.unit_price}>"


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
    def for_entity(cls, entity_type: str, entity_id: int) -> list[Journal]:
        return sess.scalars(
            select(cls).filter_by(entity_type=entity_type, entity_id=entity_id).order_by(cls.created_at)
        ).all()

    @classmethod
    def record(cls, entity_type: str, entity_id: int, field: Optional[str] = None,
               old_value: Optional[str] = None, new_value: Optional[str] = None,
               note: Optional[str] = None) -> Journal:
        entry = cls(entity_type=entity_type, entity_id=entity_id, field=field,
                    old_value=old_value, new_value=new_value, note=note)
        sess.add(entry)
        sess.flush()
        return entry

    def __repr__(self) -> str:
        target = f"{self.entity_type}#{self.entity_id}"
        if self.field:
            return f"<Journal {target}.{self.field}>"
        return f"<Journal {target}>"


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
# LogEntry
# ---------------------------------------------------------------------------

class LogEntry(Base):
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

    @classmethod
    def create(cls, body: str, domain: Optional[str] = None, context: Optional[Context] = None,
               occurred_at: Optional[datetime] = None) -> LogEntry:
        entry = cls(body=body, domain=domain, context_id=context.id if context else None,
                    occurred_at=occurred_at or _now())
        sess.add(entry)
        sess.flush()
        return entry

    @classmethod
    def recent(cls, domain: Optional[str] = None, context: Optional[Context] = None, limit: int = 20) -> list[LogEntry]:
        q = select(cls).order_by(cls.occurred_at.desc()).limit(limit)
        if domain is not None:
            q = q.where(cls.domain == domain)
        if context is not None:
            q = q.where(cls.context_id == context.id)
        return sess.scalars(q).all()

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
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # capture channel, e.g. "email", "mobile", "quick-note"
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # kind of content, e.g. "project-idea", "purchase"
    triaged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def pending(cls, category: Optional[str] = None) -> list[InboxItem]:
        q = select(cls).where(cls.triaged_at.is_(None))
        if category is not None:
            q = q.where(cls.category == category)
        return sess.scalars(q.order_by(cls.created_at)).all()

    @classmethod
    def create(cls, body: str, source: Optional[str] = None, category: Optional[str] = None) -> InboxItem:
        item = cls(body=body, source=source, category=category)
        sess.add(item)
        sess.flush()
        return item

    def triage(self) -> None:
        self.triaged_at = _now()

    def __repr__(self) -> str:
        state = "triaged" if self.triaged_at else "pending"
        tags = " ".join(f"[{t}]" for t in (self.category, self.source) if t)
        body = self.body if len(self.body) <= 60 else self.body[:60] + "…"
        return f"<InboxItem #{self.id} [{state}]{' ' + tags if tags else ''}: {body!r}>"


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
