"""HasJournal: every create, change, and delete of a journaled row is recorded with no caller
involvement, and every Journal row is attributed to the agent session that caused it."""

from typing import Iterator

import pytest
from sqlalchemy import Table, delete, update
from sqlalchemy.orm import Session

import models
from base import _now
from conftest import make_todo
from models import Context, HarnessSession, Journal, JournalAction


def _actions(session: Session, todo_id: int) -> list[tuple[JournalAction, str | None, str | None, str | None]]:
    return [
        (e.action, e.field, e.old_value, e.new_value)
        for e in Journal.for_entity(session, "Todo", todo_id, include_reads=True)
    ]


@pytest.fixture
def no_agent_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)


def test_create_is_journaled(db_session: Session, no_agent_session: None) -> None:
    todo = make_todo(db_session, "t")
    db_session.commit()
    assert _actions(db_session, todo.id) == [(JournalAction.CREATE, None, None, None)]


def test_field_change_records_old_and_new(db_session: Session, no_agent_session: None) -> None:
    todo = make_todo(db_session, "before")
    db_session.commit()
    todo.title = "after"
    db_session.commit()
    assert _actions(db_session, todo.id)[-1] == (JournalAction.UPDATE, "title", "before", "after")


def test_relationship_change_records_foreign_key(db_session: Session, no_agent_session: None) -> None:
    todo = make_todo(db_session, "t")
    other = Context.get_or_create(db_session, "elsewhere")
    db_session.commit()
    old_id = todo.context_id
    db_session.expire_all()  # the old context is no longer loaded, as in a fresh CLI process
    reloaded = db_session.get(models.Todo, todo.id)
    assert reloaded is not None
    reloaded.context = other
    db_session.commit()
    assert _actions(db_session, reloaded.id)[-1] == (JournalAction.UPDATE, "context_id", str(old_id), str(other.id))


def test_soft_delete_and_purge(db_session: Session, no_agent_session: None) -> None:
    todo = make_todo(db_session, "t")
    db_session.commit()
    todo.deleted_at = _now()
    db_session.commit()
    todo_id = todo.id
    assert [a for a, *_ in _actions(db_session, todo_id)] == [JournalAction.CREATE, JournalAction.DELETE]
    db_session.delete(todo)
    db_session.commit()
    assert _actions(db_session, todo_id) == []


def test_read_needs_an_agent_session(db_session: Session, no_agent_session: None) -> None:
    assert Journal.record_read(db_session, "Todo", 1) is None


def test_rows_are_stamped_with_the_agent_session(db_session: Session, agent_session: HarnessSession) -> None:
    todo = make_todo(db_session, "t")
    db_session.commit()
    read = Journal.record_read(db_session, "SiNode", 13)
    db_session.commit()
    assert read is not None
    assert {e.session_id for e in Journal.for_session(db_session, agent_session.id)} == {agent_session.id}
    assert [(e.entity_type, e.action) for e in Journal.for_session(db_session, agent_session.id)] == [
        ("Todo", JournalAction.CREATE),
        ("SiNode", JournalAction.READ),
    ]
    assert todo.id is not None


def test_no_agent_session_leaves_session_empty(db_session: Session, no_agent_session: None) -> None:
    todo = make_todo(db_session, "t")
    db_session.commit()
    assert [e.session_id for e in Journal.for_entity(db_session, "Todo", todo.id)] == [None]


def test_bulk_update_on_journaled_table_is_refused(db_session: Session, no_agent_session: None) -> None:
    make_todo(db_session, "t")
    db_session.commit()
    with pytest.raises(RuntimeError, match="bypass Journal"):
        db_session.execute(update(models.Todo).values(title="x"))
    with pytest.raises(RuntimeError, match="bypass Journal"):
        todo_table = models.Todo.__table__
        assert isinstance(todo_table, Table)
        db_session.execute(delete(todo_table))


def test_bulk_write_on_unjournaled_table_is_allowed(db_session: Session) -> None:
    db_session.execute(delete(models.ChannelRead))


def test_every_browsable_entity_type_is_journaled() -> None:
    from api.entities_router import ENTITY_TYPES

    assert [name for name, model in ENTITY_TYPES.items() if not issubclass(model, models.HasJournal)] == []
