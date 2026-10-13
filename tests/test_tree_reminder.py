"""tree-reminder lists the instruction-tree frontier for the current agent session: the
nodes whose parent the session has read and which it has not read itself."""

from sqlalchemy.orm import Session

from kb_cli import si_files
from kb_cli._util import journal_read
from kb_cli.hooks import _TREE_FRONTIER_REMINDER, _TREE_REMINDER, _tree_reminder_text
from models.agents.harness_session import HarnessSession

_PREFIX, _SUFFIX = _TREE_FRONTIER_REMINDER.split("{titles}")


def _read(session: Session, title: str) -> si_files.SiNode:
    node = si_files.resolve(title)
    assert node is not None
    journal_read(session, "SiNode", int(node.id))
    return node


def _listed(session: Session) -> set[str]:
    text = _tree_reminder_text(session)
    assert text.startswith(_PREFIX) and text.endswith(_SUFFIX)
    return set(text[len(_PREFIX) : -len(_SUFFIX)].split(", "))


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
