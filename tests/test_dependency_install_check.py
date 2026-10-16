"""dependency-install-check reads a Bash command on stdin and prints a block reason to stdout, so
any stdout denies the install: an audited install must leave stdout empty, even when the
LogEntry it writes resembles an earlier one."""

import argparse
import io

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conftest import inbox
from kb_cli.hooks import cmd_dependency_install_check
from kb_cli.similar import print_similar, track_new_records
from models.knowledge.log_entry import LogEntry
from models.knowledge.note import Note
from models.links.entity_link import EntityLink


def _check(command: str, session: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> str:
    """Run the hook the way the `kb` script runs any command, similarity notice included."""
    monkeypatch.setattr("sys.stdin", io.StringIO(command))
    track_new_records(session)
    cmd_dependency_install_check(argparse.Namespace(session=session))
    print_similar(session)
    return capsys.readouterr().out


def test_unaudited_install_is_blocked(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _check("cd ~/re && uv add numpy", db_session, monkeypatch, capsys).startswith("Blocked")


def test_audited_install_beside_a_similar_log_entry_prints_nothing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    note = Note.create(db_session, "Supply-chain audit: numpy", "audit", context=inbox(db_session))
    db_session.commit()
    command = f"cd ~/re && AUDITED=note{note.id} uv add numpy"
    LogEntry.create(
        db_session, f"Dependency install (audited via Note #{note.id}): {command}", context=inbox(db_session)
    )
    db_session.commit()

    assert _check(command, db_session, monkeypatch, capsys) == ""

    entries = db_session.scalars(select(LogEntry)).all()
    assert len(entries) == 2
    link = db_session.scalars(select(EntityLink).where(EntityLink.relation == "audited-by")).one()
    assert (link.type_b, link.id_b) == ("Note", note.id)


def test_install_quoted_in_a_heredoc_body_is_not_checked(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    command = "kb bug add kb 'install hook' - <<'EOF'\nan audited `uv add numpy` was blocked\nEOF\n"
    assert _check(command, db_session, monkeypatch, capsys) == ""


def test_install_in_a_heredoc_fed_to_a_shell_is_checked(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    command = "bash <<'EOF'\ncd ~/re\nuv add numpy\nEOF\n"
    assert _check(command, db_session, monkeypatch, capsys).startswith("Blocked")
