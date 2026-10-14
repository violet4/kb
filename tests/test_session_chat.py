"""list_chat_messages' offset contract: the session viewer polls a live transcript with the
returned offset, so a follow-up read must return exactly the messages appended since, and a
line the harness has not finished writing must wait for the next poll rather than being
dropped or parsed half-written. Also list_history_sessions' filters: empty transcripts appear
only on request, and the message-count and title filters keep exactly the matching ones."""

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from kb_cli import sessions
from kb_cli.sessions import list_chat_messages


def _line(role: str, text: str) -> str:
    return json.dumps({"type": role, "timestamp": "t", "message": {"role": role, "content": text}}) + "\n"


def test_offset_returns_only_appended_messages(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    path.write_text(_line("user", "one") + _line("assistant", "two"))
    first, offset = list_chat_messages(path)
    assert [m.blocks[0].text for m in first] == ["one", "two"]

    with path.open("a") as fh:
        fh.write(_line("user", "three"))
    second, offset = list_chat_messages(path, offset)
    assert [m.blocks[0].text for m in second] == ["three"]

    third, same_offset = list_chat_messages(path, offset)
    assert third == [] and same_offset == offset


def test_partial_line_waits_for_completion(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    complete = _line("user", "one")
    partial = _line("assistant", "two")
    path.write_text(complete + partial[:10])
    messages, offset = list_chat_messages(path)
    assert [m.blocks[0].text for m in messages] == ["one"]
    assert offset == len(complete.encode())

    with path.open("a") as fh:
        fh.write(partial[10:])
    messages, _ = list_chat_messages(path, offset)
    assert [m.blocks[0].text for m in messages] == ["two"]


def test_history_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    project = tmp_path / "-proj"
    project.mkdir()
    (project / "talk.jsonl").write_text(_line("user", "hello there") + _line("assistant", "hi"))
    (project / "empty.jsonl").write_text(json.dumps({"type": "summary"}) + "\n")
    monkeypatch.setattr(sessions, "_PROJECTS_DIR", tmp_path)

    assert [s.id for s in sessions.list_history_sessions(db_session)] == ["talk"]
    with_empty = sessions.list_history_sessions(db_session, include_empty=True)
    assert sorted(s.id for s in with_empty) == ["empty", "talk"]
    assert [s.id for s in sessions.list_history_sessions(db_session, include_empty=True, max_messages=0)] == ["empty"]
    assert [s.id for s in sessions.list_history_sessions(db_session, title_pattern="^HELLO")] == ["talk"]
    assert sessions.list_history_sessions(db_session, title_pattern="nomatch") == []


def test_mid_turn_message_is_a_user_message(tmp_path: Path) -> None:
    """A message typed while the agent is mid-turn is recorded as a queued_command attachment,
    not a user line; the viewer shows it as the user's message, its text carried once."""
    queued = {
        "type": "attachment",
        "timestamp": "t",
        "attachment": {"type": "queued_command", "commandMode": "prompt", "prompt": "mid-turn note"},
        "rendered": [{"content": "<system-reminder>mid-turn note</system-reminder>"}],
    }
    path = tmp_path / "s.jsonl"
    path.write_text(_line("user", "one") + json.dumps(queued) + "\n" + _line("assistant", "two"))
    messages, _ = list_chat_messages(path)
    assert [(m.role, m.blocks[0].text) for m in messages] == [
        ("user", "one"),
        ("user", "mid-turn note"),
        ("assistant", "two"),
    ]
    tags = messages[1].blocks[0].tags
    assert tags["delivered"] == "mid-turn"
    assert "mid-turn note" not in "".join(tags.values())


def test_thinking_after_the_first_block_is_a_reply(tmp_path: Path) -> None:
    """Claude Code's terminal shows a thinking block that is not the first block of its
    response as a reply, so the viewer does too; the first block stays thinking."""

    def thinking(index: int, text: str) -> str:
        message = {"role": "assistant", "content": [{"type": "thinking", "thinking": text}]}
        return json.dumps({"type": "assistant", "timestamp": "t", "apiBlockIndex": index, "message": message}) + "\n"

    path = tmp_path / "s.jsonl"
    path.write_text(thinking(0, "reasoning") + thinking(1, "Here is the answer."))
    messages, _ = list_chat_messages(path)
    blocks = [m.blocks[0] for m in messages]
    assert [(b.kind, b.text) for b in blocks] == [("thinking", "reasoning"), ("text", "Here is the answer.")]
    assert blocks[1].tags["storedAs"] == "thinking"
