"""tree-reminder lists the instruction-tree frontier for the current agent session: the
nodes whose parent the session has read and which it has not read itself, for both the
system tree (`kb si`) and the user tree (`kb i`)."""

import re

from sqlalchemy.orm import Session

from kb_cli import si_files
from kb_cli._util import journal_read
from kb_cli.hooks import (
    _TREE_FRONTIER_REMINDER,
    _TREE_REMINDER,
    _USER_TREE_FRONTIER_REMINDER,
    _USER_TREE_UNOPENED_REMINDER,
    _tree_reminder_text,
)
from models.agents.harness_session import HarnessSession
from models.knowledge.instruction import Instruction
from models.links.entity_link import EntityLink


def _read(session: Session, title: str) -> si_files.SiNode:
    node = si_files.resolve(title)
    assert node is not None
    journal_read(session, "SiNode", int(node.id))
    return node


def _listed(session: Session, template: str = _TREE_FRONTIER_REMINDER) -> set[str]:
    """The titles `template`'s sentence lists in the reminder, or an empty set if absent."""
    prefix, suffix = (re.escape(part) for part in template.split("{titles}"))
    match = re.search(prefix + "(.*?)" + suffix, _tree_reminder_text(session))
    return set(match.group(1).split(", ")) if match else set()


def _user_node(session: Session, title: str, parent: Instruction | None = None) -> Instruction:
    node = Instruction(title=title, body="b", trigger="t", write_globs="")
    session.add(node)
    session.flush()
    if parent is not None:
        EntityLink.create(session, "Instruction", parent.id, "Instruction", node.id, "parent-of")
    return node


def test_generic_reminder_before_root_is_read(db_session: Session, agent_session: HarnessSession) -> None:
    assert _tree_reminder_text(db_session) == _TREE_REMINDER


def test_lists_unread_children_of_read_nodes(db_session: Session, agent_session: HarnessSession) -> None:
    root = _read(db_session, "root")
    engineering = _read(db_session, "engineering")
    expected = {n.title for n in si_files.children_of(root.id) + si_files.children_of(engineering.id)}
    assert _listed(db_session) == expected - {"engineering"}


def test_read_node_leaves_the_list(db_session: Session, agent_session: HarnessSession) -> None:
    root = _read(db_session, "root")
    child = si_files.children_of(root.id)[-1]
    assert child.title in _listed(db_session)
    _read(db_session, child.title)
    assert child.title not in _listed(db_session)


def test_user_tree_unopened_is_named(db_session: Session, agent_session: HarnessSession) -> None:
    _read(db_session, "root")
    assert _USER_TREE_UNOPENED_REMINDER in _tree_reminder_text(db_session)


def test_user_tree_lists_unread_undeleted_children(db_session: Session, agent_session: HarnessSession) -> None:
    _read(db_session, "root")
    user_root = _user_node(db_session, "user-root")
    style = _user_node(db_session, "style", parent=user_root)
    _user_node(db_session, "shell-tools", parent=user_root)
    gone = _user_node(db_session, "retired", parent=user_root)
    gone.deleted_at = gone.created_at
    journal_read(db_session, "Instruction", user_root.id)

    assert _listed(db_session, _USER_TREE_FRONTIER_REMINDER) == {"style", "shell-tools"}
    journal_read(db_session, "Instruction", style.id)
    assert _listed(db_session, _USER_TREE_FRONTIER_REMINDER) == {"shell-tools"}
    assert _USER_TREE_UNOPENED_REMINDER not in _tree_reminder_text(db_session)
