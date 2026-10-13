"""commit-check blocks `git commit` in an agent session until that session has read the
commit-messages system instruction node, and stays silent for every other command."""

import argparse
import io
import sys

import pytest
from sqlalchemy.orm import Session

from kb_cli import si_files
from kb_cli._util import journal_read
from kb_cli.hooks import cmd_commit_check
from models import HarnessSession


def _check(session: Session, command: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> str:
    monkeypatch.setattr(sys, "stdin", io.StringIO(command))
    cmd_commit_check(argparse.Namespace(session=session))
    return capsys.readouterr().out


@pytest.mark.parametrize("command", ["git commit -m x", "git -C /repo commit -q -F -", "git add a && git commit -F -"])
def test_blocks_commit_before_reading(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    assert "kb si show commit-messages" in _check(db_session, command, monkeypatch, capsys)


@pytest.mark.parametrize("command", ["git log --oneline", "git commit-tree abc", "echo commit"])
def test_ignores_other_commands(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    assert _check(db_session, command, monkeypatch, capsys) == ""


def test_allows_commit_after_reading(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    node = si_files.resolve("commit-messages")
    assert node is not None
    journal_read(db_session, "SiNode", int(node.id))
    assert _check(db_session, "git commit -m x", monkeypatch, capsys) == ""


def test_silent_without_agent_session(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    assert _check(db_session, "git commit -m x", monkeypatch, capsys) == ""
