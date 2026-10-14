"""required-reading-check blocks a file write in an agent session until the session has read every
instruction node, in either tree, whose write-globs match the file."""

import argparse
import io
import sys

import pytest
from sqlalchemy.orm import Session

from kb_cli import si_files
from kb_cli._util import journal_read
from kb_cli.hooks import cmd_required_reading_check
from kb_cli.required_reading import command_targets, matches
from models.agents.harness_session import HarnessSession
from models.knowledge.instruction import Instruction


def _run(
    session: Session,
    stdin: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: bool = False,
) -> str:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    cmd_required_reading_check(argparse.Namespace(session=session, command=command, with_cwd=False))
    return capsys.readouterr().out


def _user_node(session: Session, write_globs: str) -> Instruction:
    node = Instruction(title="python-test", body="b", trigger="t", write_globs=write_globs)
    session.add(node)
    session.commit()
    return node


@pytest.mark.parametrize(
    ("globs", "path", "expected"),
    [
        ("*.py", "/repo/pkg/main.py", True),
        ("*.py", "main.py", True),
        ("*.md *.py", "/repo/a.py", True),
        ("*/AGENTS.md", "/repo/AGENTS.md", True),
        ("*/AGENTS.md", "/repo/docs/guide.md", False),
        ("*.py", "/repo/main.pyc", False),
        ("", "/repo/main.py", False),
    ],
)
def test_matches(globs: str, path: str, expected: bool) -> None:
    assert matches(globs, path) is expected


@pytest.mark.parametrize("path", ["/repo/README.md", "/repo/AGENTS.md", "docs/guide.md"])
def test_blocks_markdown_until_documentation_read(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    path: str,
) -> None:
    assert "kb si show documentation" in _run(db_session, path, monkeypatch, capsys)
    node = si_files.resolve("documentation")
    assert node is not None
    journal_read(db_session, "SiNode", int(node.id))
    assert _run(db_session, path, monkeypatch, capsys) == ""


@pytest.mark.parametrize("path", ["/home/u/.claude/plans/p.md", "/tmp/scratch/notes.md", "/repo/data.csv"])
def test_ignores_exempt_and_unmatched_files(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    path: str,
) -> None:
    assert _run(db_session, path, monkeypatch, capsys) == ""


def test_user_tree_node_gates_until_read(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    node = _user_node(db_session, "*.zz")
    assert "kb i show python-test" in _run(db_session, "/repo/a.zz", monkeypatch, capsys)
    journal_read(db_session, "Instruction", node.id)
    assert _run(db_session, "/repo/a.zz", monkeypatch, capsys) == ""


def test_deleted_user_node_does_not_gate(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from models.base import _now

    node = _user_node(db_session, "*.zz")
    node.deleted_at = _now()
    db_session.commit()
    assert _run(db_session, "/repo/a.zz", monkeypatch, capsys) == ""


def test_no_agent_session_never_blocks(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    assert _run(db_session, "/repo/README.md", monkeypatch, capsys) == ""


@pytest.mark.parametrize(
    ("command", "targets"),
    [
        ("text sub --file docs/a.md -i --expect 1 x y", ["docs/a.md"]),
        ("cat > docs/new.md <<'EOF'", ["docs/new.md"]),
        ("echo x | tee -a out.md", ["out.md"]),
        ("make 2>&1 | tail", []),
        ("echo x > /dev/null", []),
        ("cat docs/a.md", []),
    ],
)
def test_command_targets(command: str, targets: list[str]) -> None:
    assert command_targets(command) == targets


def test_command_mode_blocks_markdown_write(
    db_session: Session,
    agent_session: HarnessSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _run(db_session, "cat > docs/new.md <<'EOF'", monkeypatch, capsys, command=True)
    assert "docs/new.md" in out and "kb si show documentation" in out
    assert _run(db_session, "echo x > /tmp/out.md", monkeypatch, capsys, command=True) == ""


@pytest.mark.parametrize(
    ("command", "targets"),
    [
        ("cat > a.py <<'EOF'", ["/home/u/kb/a.py"]),
        ("cd /tmp/scratch && cat > hold.py <<'EOF'\nprint(1)\nEOF", ["/tmp/scratch/hold.py"]),
        ("cd sub; text sub --file x.md -i a b", ["/home/u/kb/sub/x.md"]),
        ("echo x > /abs/out.md", ["/abs/out.md"]),
        ("cd $OLDPWD && echo x > out.md", ["/home/u/kb/out.md"]),
    ],
)
def test_command_targets_resolve_against_cwd(command: str, targets: list[str]) -> None:
    """A relative target names a file in the command's directory, after any `cd` step: a
    scratch script written after `cd /tmp/...` is exempt like any other /tmp path."""
    assert command_targets(command, cwd="/home/u/kb") == targets


def test_redirect_in_a_heredoc_body_is_not_a_write() -> None:
    assert command_targets("cat > a.md <<'EOF'\necho x > b.md\nEOF", cwd="/r") == ["/r/a.md"]
