"""HasJournal: automatic Journal rows on create, field change, and soft delete."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, ClassVar, Optional, Sequence

from sqlalchemy import Delete, Table, Update, delete, event, inspect, select
from sqlalchemy.orm import MANYTOONE, Mapped, ORMExecuteState, Session, UOWTransaction
from sqlalchemy.orm.base import NO_VALUE

from models import flush_pending
from models.base import Base
from models.journal.journal import Journal, JournalAction


class HasJournal:
    """Journals every create, field change, and delete of a subclass row automatically, via
    the flush listeners in the HasJournal section below, so no command has to remember to.
    Reads are the one action a command records itself (Journal.record_read), since loading a
    row is not a write.

    A change is one UPDATE row per changed column, holding old and new values as text. A
    many-to-one relationship assignment (todo.context = ...) is recorded under its foreign
    key column, since that is what changed in the row. Setting deleted_at is a DELETE. Removing
    the row outright (purge) removes its whole journal too: a purged record was deliberately
    erased, and its id can be reused by the next row, which must not inherit its history."""

    __tablename__: str
    id: Mapped[int]

    # Bookkeeping columns rewritten as a side effect of other changes, never a change of
    # their own worth a row.
    _journal_ignored: ClassVar[frozenset[str]] = frozenset({"created_at", "updated_at", "embedding", "embedding_model"})


def _journal_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, enum.Enum):
        return str(value.value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _journal_changes(session: Session, obj: HasJournal) -> list[Journal]:
    state = inspect(obj)
    assert state is not None
    old_values: dict[str, Any] = {}
    new_values: dict[str, Any] = {}
    for attr in state.mapper.column_attrs:
        if attr.key in obj._journal_ignored:
            continue
        history = state.attrs[attr.key].history
        if history.has_changes():
            # committed_state holds the value from before the first change, or NO_VALUE when
            # the attribute was expired (e.g. by a commit) and set without being read.
            old_values[attr.key] = state.committed_state.get(attr.key, NO_VALUE)
            new_values[attr.key] = history.added[0] if history.added else None
    for rel in state.mapper.relationships:
        if rel.direction is not MANYTOONE:
            continue
        history = state.attrs[rel.key].history
        (column,) = rel.local_columns
        if history.has_changes() and column.key not in new_values:
            # The foreign key column is synced from the relationship during the flush, so
            # before it the column still holds the old id, if it is loaded at all.
            old_values[column.key] = state.dict.get(column.key, NO_VALUE)
            new = history.added[0] if history.added else None
            new_values[column.key] = new.id if new is not None else None

    unknown = [key for key, value in old_values.items() if value is NO_VALUE]
    if unknown:
        table = state.mapper.local_table
        stored = session.connection().execute(select(*(table.c[k] for k in unknown)).where(table.c.id == obj.id)).one()
        old_values.update(zip(unknown, stored))

    entity_type = type(obj).__name__
    rows = []
    changes = {key: (old_values[key], new_values[key]) for key in new_values}
    for field, (old, new) in changes.items():
        if old == new:
            continue
        if field == "deleted_at" and new is not None:
            rows.append(Journal(entity_type=entity_type, entity_id=obj.id, action=JournalAction.DELETE))
            continue
        rows.append(
            Journal(
                entity_type=entity_type,
                entity_id=obj.id,
                action=JournalAction.UPDATE,
                field=field,
                old_value=_journal_text(old),
                new_value=_journal_text(new),
            )
        )
    return rows


@event.listens_for(Session, "before_flush")
def _journal_flush(session: Session, flush_context: UOWTransaction, instances: Optional[Sequence[Any]]) -> None:
    # A new row has no id until the flush, so its CREATE row is written in after_flush;
    # changes and deletes are written here, while attribute history still holds old values.
    flush_pending.queue(session, "journal_created").extend(obj for obj in session.new if isinstance(obj, HasJournal))
    for obj in list(session.dirty):
        if isinstance(obj, HasJournal):
            session.add_all(_journal_changes(session, obj))
    for obj in list(session.deleted):
        if isinstance(obj, HasJournal):
            session.connection().execute(
                delete(Journal).where(Journal.entity_type == type(obj).__name__, Journal.entity_id == obj.id)
            )


@event.listens_for(Session, "after_flush")
def _journal_created_rows(session: Session, flush_context: UOWTransaction) -> None:
    for obj in flush_pending.take(session, "journal_created"):
        session.add(Journal(entity_type=type(obj).__name__, entity_id=obj.id, action=JournalAction.CREATE))


@event.listens_for(Session, "do_orm_execute")
def _refuse_unjournaled_bulk_write(state: ORMExecuteState) -> None:
    """A bulk UPDATE/DELETE statement (session.execute(update(Todo)...)) changes rows without
    a flush, so the HasJournal listeners never see it. Refuse it on a journaled table rather
    than let the change go unrecorded; load the rows and change their attributes instead."""
    statement = state.statement
    if not isinstance(statement, (Update, Delete)) or not isinstance(statement.table, Table):
        return
    journaled = {m.local_table for m in Base.registry.mappers if issubclass(m.class_, HasJournal)}
    if statement.table in journaled:
        verb = "UPDATE" if isinstance(statement, Update) else "DELETE"
        raise RuntimeError(
            f"bulk {verb} on {statement.table.name} would bypass Journal; load the rows and set their attributes "
            "(or session.delete() them) so HasJournal records the change"
        )
