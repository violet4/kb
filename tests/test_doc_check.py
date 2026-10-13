"""doc-path-check and doc-command-check block documentation and record-body writes in an agent
session until that session has read the documentation system instruction node."""

import argparse
import io
import sys
from typing import Callable

import pytest
from sqlalchemy.orm import Session

from kb_cli import si_files
from kb_cli._util import journal_read
from kb_cli.hooks import cmd_doc_command_check, cmd_doc_path_check
from models.agents.harness_session import HarnessSession


def _run(
    cmd: Callable[[argparse.Namespace], None],
    session: Session,
    stdin: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    cmd(argparse.Namespace(session=session))
    return capsys.readouterr().out


@pytest.mark.parametrize("path", ["/repo/README.md", "/repo/AGENTS.md", "docs/guide.MD"])
def test_path_blocks_markdown(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    path: str,
) -> None:
    assert "kb si show documentation" in _run(cmd_doc_path_check, db_session, path, monkeypatch, capsys)


@pytest.mark.parametrize("path", ["/repo/main.py", "/home/u/.claude/plans/p.md", "/tmp/scratch/notes.md"])
def test_path_ignores_code_and_harness_files(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    path: str,
) -> None:
    assert _run(cmd_doc_path_check, db_session, path, monkeypatch, capsys) == ""


@pytest.mark.parametrize(
    "command",
    [
        "kb notes add kb 'title' - <<'EOF'",
        "kb todo update 355 --notes -",
        "kb journal add Goal 23 -",
        "kb si edit root --replace a b",
        "text sub --file docs/a.md -i --expect 1 x y",
        "cat > docs/new.md <<'EOF'",
    ],
)
def test_command_blocks_record_and_markdown_writes(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    assert "kb si show documentation" in _run(cmd_doc_command_check, db_session, command, monkeypatch, capsys)


@pytest.mark.parametrize(
    "command",
    [
        "kb todo show 355",
        "kb si show root",
        "text sub --file kb_cli/hooks.py -i --expect 1 x y",
        "cat docs/a.md",
        "echo x > /tmp/out.md",
    ],
)
def test_command_ignores_reads_and_code_edits(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    assert _run(cmd_doc_command_check, db_session, command, monkeypatch, capsys) == ""


def test_allowed_after_reading_documentation(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    node = si_files.resolve("documentation")
    assert node is not None
    journal_read(db_session, "SiNode", int(node.id))
    assert _run(cmd_doc_path_check, db_session, "/repo/README.md", monkeypatch, capsys) == ""
    assert _run(cmd_doc_command_check, db_session, "kb todo update 1 --notes -", monkeypatch, capsys) == ""
