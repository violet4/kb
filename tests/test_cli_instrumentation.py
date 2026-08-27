"""Tests for the kb <-> cli_instrumentation integration: the payload-to-CliInvocation
mapping (kb_cli.cli_instrumentation_sink), and subcommand-path resolution against kb's
own real subparser tree (kb_cli.todo, not a synthetic fixture) -- catches drift if kb's
subparser dest-naming convention (dest="cmd" reused at every level, see kb_cli/todo.py)
ever changes in a way cli_instrumentation's _resolved_subcommand heuristic can't follow.

Does not shell out to `./kb` as a subprocess: the `kb` script itself is not importable
(no .py extension, and importing it would execute top-level argument parsing against the
real on-disk database at models.py's hardcoded _DB_PATH, which has no test-time override).
"""

import argparse
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from cli_instrumentation import InstrumentedArgumentParser, attach_recording, instrumented_run

from kb_cli import stats, todo
from kb_cli.cli_instrumentation_sink import invocation_kwargs, should_record
from models import CliInvocation


def test_should_record_excludes_successful_hooks_invocations() -> None:
    assert should_record({"command": "hooks daily-check", "success": True}) is False


def test_should_record_keeps_failing_hooks_invocations() -> None:
    assert should_record({"command": "hooks session-inbox-check", "success": False}) is True


def test_should_record_keeps_successful_non_hooks_invocations() -> None:
    assert should_record({"command": "todo add buy salt", "success": True}) is True


def test_should_record_does_not_prefix_match_hooks() -> None:
    """ "hooksomething" must not be excluded by a substring/prefix match against
    "hooks" -- only an exact top-level-subcommand-word match counts."""
    assert should_record({"command": "hooksomething", "success": True}) is True


def test_invocation_kwargs_maps_success_payload() -> None:
    payload = {
        "command": "todo add buy salt",
        "subcommand": "todo.add",
        "success": True,
        "duration_ms": 42,
        "args": {"title": "buy salt", "urgent": False},
    }
    kwargs = invocation_kwargs(payload)
    assert kwargs["command"] == "todo add buy salt"
    assert kwargs["subcommand"] == "todo.add"
    assert kwargs["success"] is True
    assert kwargs["error"] is None
    assert kwargs["duration_ms"] == 42
    assert '"title": "buy salt"' in kwargs["args_json"]


def test_invocation_kwargs_maps_failure_payload() -> None:
    payload = {
        "command": "todo add",
        "success": False,
        "error": "the following arguments are required: title",
        "duration_ms": 0,
    }
    kwargs = invocation_kwargs(payload)
    assert kwargs["success"] is False
    assert kwargs["error"] == "the following arguments are required: title"
    assert kwargs["subcommand"] is None
    assert kwargs["args_json"] == "{}"


def test_invocation_kwargs_writes_a_real_row(db_session: Session) -> None:
    kwargs = invocation_kwargs(
        {"command": "todo add x", "subcommand": "todo.add", "success": True, "duration_ms": 5, "args": {}}
    )
    db_session.add(CliInvocation(**kwargs))
    db_session.commit()

    row = db_session.scalars(select(CliInvocation)).one()
    assert row.command == "todo add x"
    assert row.subcommand == "todo.add"


def _build_kb_subparser_tree() -> argparse.ArgumentParser:
    """Builds the real kb_cli.todo subparser tree the same way the `kb` script does
    (todo.add_subparser(subparsers)), not a synthetic stand-in -- so a change to kb's
    own dest-naming convention (dest="cmd" reused at every level) is caught here, not
    only by cli_instrumentation's own generic unit tests."""
    parser = InstrumentedArgumentParser(prog="kb")
    subparsers = parser.add_subparsers(dest="command", required=True)
    todo.add_subparser(subparsers)
    return parser


def test_subcommand_resolves_todo_add_against_real_kb_subparser_tree() -> None:
    parser = _build_kb_subparser_tree()
    records: list[dict[str, Any]] = []
    attach_recording(parser, record=records.append)

    args = parser.parse_args(["todo", "add", "buy salt"])
    args.func = lambda a: None  # kb_cli.todo's real cmd_add needs args.session/context; not exercised here
    with instrumented_run(parser, args, record=records.append):
        args.func(args)

    assert len(records) == 1
    assert records[0]["subcommand"] == "todo.add"
    assert records[0]["success"] is True


def test_parse_error_on_missing_title_still_resolves_subcommand() -> None:
    """A parse-time failure inside `todo add`'s own subparser raises before
    args.command/args.cmd are ever populated -- cli_instrumentation resolves
    `subcommand` from the failing subparser's own `prog` string instead
    ("kb todo add" -> "todo.add") for exactly this case (see its 0.0.7 changelog
    entry)."""
    parser = _build_kb_subparser_tree()
    records: list[dict[str, Any]] = []
    attach_recording(parser, record=records.append)

    try:
        parser.parse_args(["todo", "add"])
    except SystemExit:
        pass

    assert len(records) == 1
    assert records[0]["success"] is False
    assert records[0]["subcommand"] == "todo.add"
    assert "title" in records[0]["error"]


def test_rows_from_session_returns_shaped_dicts(db_session: Session) -> None:
    db_session.add(CliInvocation(command="todo add x", subcommand="todo.add", success=True, duration_ms=5))
    db_session.add(
        CliInvocation(command="todo add", subcommand="todo.add", success=False, error="missing title", duration_ms=0)
    )
    db_session.commit()

    since = datetime(2000, 1, 1, tzinfo=timezone.utc)  # before both rows -- both must be included
    rows = stats._rows_from_session(db_session, since)

    assert len(rows) == 2
    assert {r["subcommand"] for r in rows} == {"todo.add"}
    assert {r["success"] for r in rows} == {True, False}
    assert any(r["error"] == "missing title" for r in rows)


def test_rows_from_session_excludes_rows_before_since(db_session: Session) -> None:
    db_session.add(CliInvocation(command="todo add x", subcommand="todo.add", success=True, duration_ms=5))
    db_session.commit()

    since = datetime(2999, 1, 1, tzinfo=timezone.utc)  # after the row -- must be excluded
    rows = stats._rows_from_session(db_session, since)

    assert rows == []


def test_kb_stats_subparser_wires_instrumentation_leaf(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`kb stats instrumentation` (kb_cli/stats.py's add_subparser) must actually reach
    cli_instrumentation.stats.render_report -- exercised here against a fake fetch_rows
    (not _fetch_instrumentation_rows, which hits the real on-disk DB via SessionFactory,
    same reason this file never shells out to `./kb` itself)."""

    def fake_fetch_rows(since: Any) -> list[dict[str, Any]]:
        return [{"command": "todo add x", "subcommand": "todo.add", "success": True, "error": None, "duration_ms": 1}]

    monkeypatch.setattr(stats, "_fetch_instrumentation_rows", fake_fetch_rows)

    parser = argparse.ArgumentParser(prog="kb")
    subparsers = parser.add_subparsers(dest="command", required=True)
    stats.add_subparser(subparsers)

    args = parser.parse_args(["stats", "instrumentation", "--days", "1"])
    args.func(args)

    out = capsys.readouterr().out
    assert "1 invocation(s), 0 error(s)" in out
    assert "todo.add" in out
