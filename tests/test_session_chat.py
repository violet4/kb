"""list_chat_messages' offset contract: the session viewer polls a live transcript with the
returned offset, so a follow-up read must return exactly the messages appended since, and a
line the harness has not finished writing must wait for the next poll rather than being
dropped or parsed half-written."""

import json
from pathlib import Path

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
