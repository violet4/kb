"""HarnessSession liveness: a session is live only while the process that registered it is
still running, identified by pid and start time, and only until another session registers in
the same process (`/clear`, `/resume`). live() stamps ended_at on each session it finds ended
and never checks that row again."""

import os
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from models import HarnessSession

PID = os.getpid()


def _register(session: Session, harness_id: str) -> HarnessSession:
    row = HarnessSession.register(session, harness_id, cwd="/", pid=PID)
    session.commit()
    return row


def test_registered_session_is_live(db_session: Session) -> None:
    row = _register(db_session, "a")
    assert HarnessSession.live(db_session) == [row]


def test_new_session_in_same_process_ends_the_previous(db_session: Session) -> None:
    first = _register(db_session, "a")
    second = _register(db_session, "b")
    assert first.ended_at is not None
    assert HarnessSession.live(db_session) == [second]


def test_resume_reopens_and_ends_the_other(db_session: Session) -> None:
    first = _register(db_session, "a")
    second = _register(db_session, "b")
    _register(db_session, "a")
    assert first.ended_at is None and second.ended_at is not None
    assert HarnessSession.live(db_session) == [first]


def test_reused_pid_is_not_live_and_is_stamped(db_session: Session) -> None:
    row = _register(db_session, "a")
    assert row.process_started_at is not None
    # The process now at this pid started after the registered one: a reuse.
    row.process_started_at -= timedelta(days=1)
    db_session.commit()
    assert HarnessSession.live(db_session) == []
    assert row.ended_at is not None


def test_ended_row_is_not_checked_again(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    row = _register(db_session, "a")
    assert row.process_started_at is not None
    row.process_started_at -= timedelta(days=1)
    db_session.commit()
    HarnessSession.live(db_session)

    def fail(self: HarnessSession) -> bool:
        raise AssertionError(f"is_alive() called for ended row {self.harness_id}")

    monkeypatch.setattr(HarnessSession, "is_alive", fail)
    assert HarnessSession.live(db_session) == []
