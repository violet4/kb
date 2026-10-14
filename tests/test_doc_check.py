"""doc-command-check blocks kb record-body writes in an agent session until that session has read
the documentation system instruction node. Markdown file writes are gated by
required-reading-check instead (tests/test_required_reading.py)."""

import argparse
import io
import sys

import pytest
from sqlalchemy.orm import Session

from kb_cli import si_files
from kb_cli._util import journal_read
from kb_cli.hooks import cmd_doc_command_check
from models.agents.harness_session import HarnessSession


def _run(session: Session, stdin: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> str:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    cmd_doc_command_check(argparse.Namespace(session=session))
    return capsys.readouterr().out


@pytest.mark.parametrize(
    "command",
    [
        "kb notes add kb 'title' - <<'EOF'",
        "kb todo update 355 --notes -",
        "kb journal add Goal 23 -",
        "kb si edit root --replace a b",
    ],
)
def test_blocks_record_writes(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    assert "kb si show documentation" in _run(db_session, command, monkeypatch, capsys)


@pytest.mark.parametrize("command", ["kb todo show 355", "kb si show root", "cat docs/a.md"])
def test_ignores_reads(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    assert _run(db_session, command, monkeypatch, capsys) == ""


def test_allowed_after_reading_documentation(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    node = si_files.resolve("documentation")
    assert node is not None
    journal_read(db_session, "SiNode", int(node.id))
    assert _run(db_session, "kb todo update 1 --notes -", monkeypatch, capsys) == ""
