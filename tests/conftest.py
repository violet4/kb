"""Shared pytest fixtures: an isolated in-memory database per test.

models.py's sess/_engine are module-level singletons bound to the real kb.db at
import time, so isolating a test means swapping both out for an in-memory engine
for the duration of the test, then restoring the originals -- never touching the
real database.
"""
import sys
from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
import models_pg  # noqa: F401 -- registers PG tables on Base.metadata
from base import Base


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    SessionFactory = scoped_session(sessionmaker(bind=engine))
    test_sess = SessionFactory()

    Base.metadata.create_all(engine)

    original_engine = models._engine
    original_sess = models.sess
    models._engine = engine
    models.sess = test_sess

    try:
        yield test_sess
    finally:
        test_sess.close()
        models._engine = original_engine
        models.sess = original_sess
