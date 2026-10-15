"""When the web UI may submit a prompt to, or press Esc in, a live `kb claude` session. A prompt
submitted while a permission dialog is open would answer the dialog, so a prompt is allowed
mid-turn only in a session that reports permission prompts and has none flagged; anything not
known to be safe is refused."""

import argparse
import os

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

import harness_input
from kb_cli.hooks import cmd_permission_request, cmd_session_inbox_check, cmd_session_stop
from api.sessions_router import SessionRenameIn, post_session_rename
from kb_cli.sessions import interrupt_blocker, prompt_blocker, rename_blocker
from models.agents.harness_session import HarnessSession, HarnessSessionStatus


@pytest.fixture
def wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harness_input, "accepts_input", lambda pid: True)


def _row(
    session: Session,
    status: HarnessSessionStatus,
    reports: bool = True,
    awaiting: bool = False,
) -> HarnessSession:
    row = HarnessSession.register(session, "s", cwd="/", pid=os.getpid(), reports_permission_prompts=reports)
    row.status = status
    row.awaiting_permission = awaiting
    session.commit()
    return row


def test_unwrapped_session_takes_neither(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harness_input, "accepts_input", lambda pid: False)
    row = _row(db_session, HarnessSessionStatus.INFERRING)
    assert "kb claude --resume s" in (prompt_blocker(row) or "")
    assert "kb claude --resume s" in (interrupt_blocker(row) or "")


def test_idle_session_takes_a_prompt_but_not_esc(db_session: Session, wrapped: None) -> None:
    row = _row(db_session, HarnessSessionStatus.IDLE, reports=False)
    assert prompt_blocker(row) is None
    assert interrupt_blocker(row) is not None


def test_busy_session_takes_a_prompt_only_when_it_reports_permission_prompts(
    db_session: Session, wrapped: None
) -> None:
    assert prompt_blocker(_row(db_session, HarnessSessionStatus.INFERRING, reports=True)) is None
    assert prompt_blocker(_row(db_session, HarnessSessionStatus.INFERRING, reports=False)) is not None


def test_flagged_permission_prompt_blocks_prompts_but_not_esc(db_session: Session, wrapped: None) -> None:
    row = _row(db_session, HarnessSessionStatus.INFERRING, awaiting=True)
    assert "permission prompt" in (prompt_blocker(row) or "")
    assert interrupt_blocker(row) is None


def test_only_an_idle_session_takes_a_rename(db_session: Session, wrapped: None) -> None:
    assert rename_blocker(_row(db_session, HarnessSessionStatus.IDLE)) is None
    assert rename_blocker(_row(db_session, HarnessSessionStatus.INFERRING)) is not None


def test_rename_sends_one_line_and_leaves_the_session_idle(
    db_session: Session, wrapped: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(harness_input, "send", lambda pid, text: sent.append(text))
    row = _row(db_session, HarnessSessionStatus.IDLE)
    post_session_rename("s", SessionRenameIn(title="  new\nname\t here "), session=db_session)
    assert sent == ["/rename new name here"]
    assert row.status == HarnessSessionStatus.IDLE


def test_rename_refuses_an_empty_title(db_session: Session, wrapped: None) -> None:
    _row(db_session, HarnessSessionStatus.IDLE)
    with pytest.raises(HTTPException) as exc:
        post_session_rename("s", SessionRenameIn(title=" \n\x01 "), session=db_session)
    assert exc.value.status_code == 422


@pytest.fixture
def hook_args(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> argparse.Namespace:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s")
    return argparse.Namespace(session=db_session)


def test_permission_request_hook_sets_the_flag_and_turn_end_clears_it(
    db_session: Session, hook_args: argparse.Namespace
) -> None:
    row = _row(db_session, HarnessSessionStatus.INFERRING)
    cmd_permission_request(hook_args)
    assert row.awaiting_permission
    cmd_session_stop(hook_args)
    assert not row.awaiting_permission
    assert row.status == HarnessSessionStatus.IDLE


def test_next_prompt_clears_the_flag(db_session: Session, hook_args: argparse.Namespace) -> None:
    row = _row(db_session, HarnessSessionStatus.INFERRING, awaiting=True)
    cmd_session_inbox_check(hook_args)
    assert not row.awaiting_permission


def test_reregistering_without_the_flag_value_keeps_it(db_session: Session) -> None:
    row = _row(db_session, HarnessSessionStatus.IDLE, reports=True)
    HarnessSession.register(db_session, "s", cwd="/", pid=os.getpid())
    assert row.reports_permission_prompts
    HarnessSession.register(db_session, "s", cwd="/", pid=os.getpid(), reports_permission_prompts=False)
    assert not row.reports_permission_prompts
