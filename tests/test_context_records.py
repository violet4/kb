"""What is filed in a context: every model with a context_id counts, so `context show` lists it,
`merge` moves it, and `rm` refuses while it is there."""

import argparse

import pytest
from sqlalchemy.orm import Session

from kb_cli.context_cmd import cmd_merge, cmd_rm, cmd_show
from models.context import Context, ContextTag
from models.knowledge.note import Collection, Note
from models.work.event import Event
from models.knowledge.instruction import Instruction
from conftest import make_todo


def _note(session: Session, context: Context) -> Note:
    note = Note(title="n", body="b", collection=Collection.INBOX, context_id=context.id)
    session.add(note)
    session.flush()
    return note


def test_filed_models_cover_every_context_id_model_but_context_tag() -> None:
    models = Context.filed_models()
    assert {Note, Event, Instruction} <= set(models)
    assert ContextTag not in models


def test_merge_moves_a_note(db_session: Session) -> None:
    source, target = Context.create(db_session, "src"), Context.create(db_session, "dst")
    note = _note(db_session, source)
    cmd_merge(argparse.Namespace(session=db_session, name="src", into="dst"))
    assert note.context_id == target.id


def test_rm_refuses_a_context_holding_only_a_note(db_session: Session) -> None:
    context = Context.create(db_session, "src")
    _note(db_session, context)
    with pytest.raises(SystemExit):
        cmd_rm(argparse.Namespace(session=db_session, name="src"))


def test_show_subtree_lists_records_of_sub_contexts(db_session: Session, capsys: pytest.CaptureFixture[str]) -> None:
    parent = Context.create(db_session, "parent")
    child = Context.create(db_session, "child", parent=parent)
    todo = make_todo(db_session, "t", context=child)
    _note(db_session, parent)
    cmd_show(argparse.Namespace(session=db_session, name="parent", subtree=True))
    out = capsys.readouterr().out
    assert "2 connected entities across 2 contexts" in out
    assert "Note: 1, Todo: 1" in out
    assert f"Todo:{todo.id} " in out and "[child]" in out
