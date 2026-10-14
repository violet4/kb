"""uv-sync-check reads "<command>\\n<cwd>" on stdin, where the command itself can span lines (a
heredoc, a multi-step script), so the cwd is the last line, and a `uv sync` on any line of the
command is caught."""

import argparse
import io

import pytest

from kb_cli.hooks import cmd_uv_sync_check


def _check(stdin: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> str:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    cmd_uv_sync_check(argparse.Namespace())
    return capsys.readouterr().out


def test_blocks_uv_sync_in_kb(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert _check("uv sync\n/home/u/kb", monkeypatch, capsys)


def test_blocks_uv_sync_on_a_later_line(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert _check("echo start\nuv sync\n/home/u/kb", monkeypatch, capsys)


def test_cwd_is_the_last_line(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # The command mentions no kb path; only the cwd, on the last line, puts it in ~/kb.
    assert _check("echo start\nuv sync\n/home/u/kb", monkeypatch, capsys)
    assert not _check("echo start\nuv sync\n/home/u/other", monkeypatch, capsys)


def test_confirmed_sync_is_allowed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert not _check("UV_SYNC_CONFIRMED=1 uv sync\n/home/u/kb", monkeypatch, capsys)


def test_heredoc_body_is_not_a_command(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # A commit message that mentions the command does not run it.
    message = "git commit -F - <<'EOF'\nfix the uv sync check\nEOF\n/home/u/kb"
    assert not _check(message, monkeypatch, capsys)
