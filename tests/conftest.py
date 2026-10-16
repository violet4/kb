"""Shared pytest fixtures: an isolated in-memory database per test.

Model methods take `session: Session` as an explicit parameter (per SQLAlchemy's own
session-lifecycle guidance), so isolating a test is just constructing a fresh Session
bound to a fresh in-memory engine -- no monkey-patching of module globals needed.
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.base import Base
from models.db import load_sqlite_vec

if TYPE_CHECKING:
    from models.agents.harness_session import HarnessSession
    from models.context import Context
    from models.work.daily import Daily
    from models.work.todo import Todo


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", load_sqlite_vec)
    Base.metadata.create_all(engine)

    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def agent_session(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator["HarnessSession"]:
    """A registered agent session that this process detects as its own."""
    import models.journal.journal
    from models.agents.harness_session import HarnessSession

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session")
    monkeypatch.setattr(models.journal.journal, "_session_keys", {})
    row = HarnessSession.register(db_session, "test-session", cwd="/", pid=1)
    db_session.commit()
    yield row


def inbox(session: Session) -> "Context":
    """Every Todo/Daily/Note/... must be placed in a context; tests that don't care use `inbox`."""
    from models.context import Context

    return Context.get_or_create(session, "inbox")


def make_daily(session: Session, *args: Any, **kwargs: Any) -> "Daily":
    from models.work.daily import Daily

    kwargs.setdefault("context", inbox(session))
    return Daily.create(session, *args, **kwargs)


def make_todo(session: Session, *args: Any, **kwargs: Any) -> "Todo":
    from models.work.todo import Todo

    kwargs.setdefault("context", inbox(session))
    return Todo.create(session, *args, **kwargs)
