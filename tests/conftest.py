"""Shared pytest fixtures: an isolated in-memory database per test.

Model methods take `session: Session` as an explicit parameter (per SQLAlchemy's own
session-lifecycle guidance), so isolating a test is just constructing a fresh Session
bound to a fresh in-memory engine -- no monkey-patching of module globals needed.
"""

import sys
from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models_pg  # noqa: F401 -- registers PG tables on Base.metadata
from base import Base


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
