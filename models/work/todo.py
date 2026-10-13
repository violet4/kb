"""Todo, a committed next action."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Sequence

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base, UtcDateTime, _now
from models.behaviors.embedding import HasEmbedding
from models.behaviors.placement import HasContextOrTag
from models.context import Context, Tag
from models.journal.tracking import HasJournal
from models.links.auto_links import HasAutoLinks
from models.work.wishlist import WishlistEffort

if TYPE_CHECKING:
    from models.work.goal import Goal


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


class Todo(Base, HasContextOrTag, HasEmbedding, HasAutoLinks, HasJournal):
    __tablename__ = "todo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[TodoStatus] = mapped_column(
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
    defer_until: Mapped[Optional[datetime]] = mapped_column(UtcDateTime(), nullable=True)
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
        use the latter for a context-plus-sub-contexts filter.
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
            q = q.where(matches)
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

    def triage_key(self) -> tuple[bool, int, int, bool, int]:
        """Sort key for a triage list: urgent first, then resolution distance (mechanical
        first), severity (critical first), bugs before other kinds, newest first. Ranks
        follow each enum's declaration order; an unset field sorts after every set value."""
        distances = list(TodoResolutionDistance)
        severities = list(reversed(TodoSeverity))
        return (
            not self.urgent,
            distances.index(self.resolution_distance) if self.resolution_distance else len(distances),
            severities.index(self.severity) if self.severity else len(severities),
            self.kind is not TodoKind.BUG,
            -self.id,
        )

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
