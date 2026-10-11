"""Shared pytest fixtures: an isolated in-memory database per test.

Model methods take `session: Session` as an explicit parameter (per SQLAlchemy's own
session-lifecycle guidance), so isolating a test is just constructing a fresh Session
bound to a fresh in-memory engine -- no monkey-patching of module globals needed.
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models_pg  # noqa: F401 -- registers PG tables on Base.metadata
from base import Base

if TYPE_CHECKING:
    from models import Context, Daily, Todo


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def inbox(session: Session) -> "Context":
    """Every Todo/Daily/Note/... must be placed in a context; tests that don't care use `inbox`."""
    from models import Context

    return Context.get_or_create(session, "inbox")


def make_daily(session: Session, *args: Any, **kwargs: Any) -> "Daily":
    from models import Daily

    kwargs.setdefault("context", inbox(session))
    return Daily.create(session, *args, **kwargs)


def make_todo(session: Session, *args: Any, **kwargs: Any) -> "Todo":
    from models import Todo

    kwargs.setdefault("context", inbox(session))
    return Todo.create(session, *args, **kwargs)
