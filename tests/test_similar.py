"""After a command creates a record, kb names existing records of the same type that are close
to it, so a duplicate is noticed when it is made."""

import pytest
from sqlalchemy.orm import Session

from kb_cli.similar import print_similar, track_new_records
from conftest import make_todo


def test_new_record_names_a_close_existing_one(db_session: Session, capsys: pytest.CaptureFixture[str]) -> None:
    existing = make_todo(db_session, "buy salt")
    db_session.flush()
    track_new_records(db_session)
    make_todo(db_session, "buy salt")
    db_session.flush()

    print_similar(db_session)

    # On stderr: stdout is the command's result, which a hook adapter reads as a block reason.
    captured = capsys.readouterr()
    assert f"similar existing Todo #{existing.id} 'buy salt'" in captured.err and captured.out == ""


def test_unrelated_record_prints_nothing(db_session: Session, capsys: pytest.CaptureFixture[str]) -> None:
    make_todo(db_session, "buy salt")
    db_session.flush()
    track_new_records(db_session)
    make_todo(db_session, "reticulate the quantum flux capacitor")
    db_session.flush()

    print_similar(db_session)

    assert capsys.readouterr().err == ""


def test_records_created_before_tracking_are_not_reported(
    db_session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    make_todo(db_session, "buy salt")
    make_todo(db_session, "buy salt")
    db_session.flush()
    track_new_records(db_session)

    print_similar(db_session)

    assert capsys.readouterr().err == ""
