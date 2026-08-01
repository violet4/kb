"""Todo.urgent: the URGENT summary section must bypass context scope and defer_until
entirely (that's its whole purpose -- see Goal #28), so those two bypasses are the
cases worth locking down, plus the ordinary on/off/non-urgent-excluded behavior.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import Context, Todo, TodoStatus


def test_urgent_pending_excludes_non_urgent(db_session: Session) -> None:
    Todo.create(db_session, "not urgent")
    db_session.commit()
    assert Todo.urgent_pending(db_session) == []


def test_urgent_pending_includes_urgent(db_session: Session) -> None:
    todo = Todo.create(db_session, "urgent thing", urgent=True)
    db_session.commit()
    assert Todo.urgent_pending(db_session) == [todo]


def test_urgent_pending_ignores_context(db_session: Session) -> None:
    other = Context.get_or_create(db_session, "elsewhere")
    db_session.commit()
    todo = Todo.create(db_session, "urgent elsewhere", context=other, urgent=True)
    db_session.commit()
    # No context filter is passed at all -- urgent_pending has no context param.
    assert todo in Todo.urgent_pending(db_session)


def test_urgent_pending_ignores_future_defer_until(db_session: Session) -> None:
    future = datetime.now(timezone.utc) + timedelta(days=30)
    todo = Todo.create(db_session, "urgent but deferred", urgent=True, defer_until=future)
    db_session.commit()
    assert todo in Todo.urgent_pending(db_session)
    # Contrast: the same defer_until *does* hide a non-urgent Todo from .active().
    non_urgent = Todo.create(db_session, "deferred, not urgent", defer_until=future)
    db_session.commit()
    assert non_urgent not in Todo.active(db_session)


def test_urgent_pending_excludes_done(db_session: Session) -> None:
    todo = Todo.create(db_session, "urgent but done", urgent=True)
    todo.status = TodoStatus.DONE
    db_session.commit()
    assert todo not in Todo.urgent_pending(db_session)
