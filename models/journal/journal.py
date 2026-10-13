"""Journal, the structured activity history of every journaled record."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, NamedTuple, Optional, Sequence

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, case, event, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from harness import current_session_id
from models.agents.harness_session import HarnessSession
from models.base import Base

# Journal — structured activity history for any entity, keyed by (entity_type,
# entity_id). Distinct from LogEntry (a fact about the world, not about a
# specific record) and from Note (durable reference knowledge, not history).


class JournalAction(enum.Enum):
    """What happened to a Journal row's entity. CREATE/UPDATE/DELETE are written by the
    HasJournal listener, READ by a `show` command run inside an agent session, NOTE by a
    hand-written entry (`kb journal add`)."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    NOTE = "note"


class TouchedRecord(NamedTuple):
    """One record as a session touched it: changed is False when the session only read it."""

    entity_type: str
    entity_id: int
    changed: bool
    last_at: datetime


class Journal(Base):
    """One event in an entity's history: its creation, a field change (field/old_value/
    new_value), a deletion, a read, or a free-text note. session_id names the agent session
    that caused it, filled in automatically on insert (see _stamp_journal_session) and NULL
    for anything done outside a registered session, such as the web UI. Indexed by session
    so one session's whole trajectory is a single query, and by entity for an entity's
    history.

    entity_type/entity_id address any row in any table, with no foreign key, the same way
    EntityLink does. That also covers records outside the database: an si node is
    ("SiNode", its numeric file id)."""

    __tablename__ = "journal"
    __table_args__ = (Index("ix_journal_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[JournalAction] = mapped_column(
        Enum(JournalAction, create_constraint=True, validate_strings=True), nullable=False
    )
    field: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("harness_session.id"), nullable=True, index=True
    )

    harness_session: Mapped[Optional[HarnessSession]] = relationship("HarnessSession")

    @classmethod
    def for_entity(
        cls, session: Session, entity_type: str, entity_id: int, include_reads: bool = False
    ) -> Sequence[Journal]:
        """An entity's history, oldest first. Reads are left out unless asked for: they say
        who looked, not what changed, and a frequently consulted record has far more of them."""
        q = select(cls).filter_by(entity_type=entity_type, entity_id=entity_id)
        if not include_reads:
            q = q.where(cls.action != JournalAction.READ)
        return session.scalars(q.order_by(cls.created_at, cls.id)).all()

    @classmethod
    def for_session(cls, session: Session, session_id: int) -> Sequence[Journal]:
        """Everything one agent session did to kb records, oldest first: its trajectory."""
        return session.scalars(select(cls).where(cls.session_id == session_id).order_by(cls.created_at, cls.id)).all()

    @classmethod
    def read_ids(cls, session: Session, entity_type: str, session_id: int) -> set[int]:
        """The ids of every entity_type record one agent session has read."""
        return set(
            session.scalars(
                select(cls.entity_id).where(
                    cls.session_id == session_id,
                    cls.entity_type == entity_type,
                    cls.action == JournalAction.READ,
                )
            )
        )

    @classmethod
    def touched_by(cls, session: Session, session_id: int) -> list[TouchedRecord]:
        """Every distinct record one agent session has touched, most recently touched first."""
        last_at = func.max(cls.created_at)
        changes = func.sum(case((cls.action == JournalAction.READ, 0), else_=1))
        rows = session.execute(
            select(cls.entity_type, cls.entity_id, changes, last_at)
            .where(cls.session_id == session_id)
            .group_by(cls.entity_type, cls.entity_id)
            .order_by(last_at.desc())
        )
        return [TouchedRecord(t, i, bool(n), at) for t, i, n, at in rows]

    def describe(self) -> str:
        """One line naming what happened, without timestamp or session."""
        if self.action is JournalAction.UPDATE and self.field:
            text = f"{self.field}: {self.old_value!r} -> {self.new_value!r}"
        elif self.action is JournalAction.NOTE:
            text = self.note or ""
        else:
            text = {
                JournalAction.CREATE: "created",
                JournalAction.READ: "read",
                JournalAction.DELETE: "deleted",
                JournalAction.UPDATE: "updated",
            }[self.action]
        if self.note and self.action is not JournalAction.NOTE:
            text += f" ({self.note})"
        return text

    @classmethod
    def record(
        cls,
        session: Session,
        entity_type: str,
        entity_id: int,
        action: JournalAction = JournalAction.NOTE,
        field: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Journal:
        entry = cls(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            field=field,
            old_value=old_value,
            new_value=new_value,
            note=note,
        )
        session.add(entry)
        session.flush()
        return entry

    @classmethod
    def record_read(cls, session: Session, entity_type: str, entity_id: int) -> Optional[Journal]:
        """A READ row, written only inside an agent session: a read is worth recording as part
        of a session's trajectory, and a read with no session (the web UI, a plain shell) has
        nothing to attribute it to."""
        if current_session_id() is None:
            return None
        return cls.record(session, entity_type, entity_id, action=JournalAction.READ)

    def __repr__(self) -> str:
        target = f"{self.entity_type}#{self.entity_id}"
        if self.field:
            return f"<Journal {self.action.value} {target}.{self.field}>"
        return f"<Journal {self.action.value} {target}>"


# The integer key of each harness session already looked up by this process. A session's
# row never changes key, so a hit is cached for the life of the process; a miss is not,
# since the session may register later.
_session_keys: dict[str, int] = {}


def _current_session_key(connection: Any) -> Optional[int]:
    harness_id = current_session_id()
    if harness_id is None:
        return None
    if harness_id not in _session_keys:
        key = connection.scalar(select(HarnessSession.id).where(HarnessSession.harness_id == harness_id))
        if key is None:
            return None
        _session_keys[harness_id] = key
    return _session_keys[harness_id]


@event.listens_for(Journal, "before_insert")
def _stamp_journal_session(mapper: Any, connection: Any, target: Journal) -> None:
    if target.session_id is None:
        target.session_id = _current_session_key(connection)
