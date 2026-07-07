"""Verifies the in-memory test DB fixture itself works before trusting it for real tests."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Daily


def test_fixture_gives_isolated_empty_db(db_session: Session) -> None:
    assert db_session.scalars(select(Daily)).all() == []
    daily = Daily.create("test daily")
    db_session.commit()
    assert daily.id is not None


def test_fixture_does_not_leak_between_tests(db_session: Session) -> None:
    # If the previous test's data leaked through, this table wouldn't be empty.
    assert db_session.scalars(select(Daily)).all() == []
