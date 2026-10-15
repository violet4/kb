"""HasAutoLinks: a TYPE:ID reference in a row's text becomes a "mentions" EntityLink, and editing
the reference out removes the link."""

from sqlalchemy.orm import Session

from conftest import inbox, make_todo
from models.knowledge.log_entry import LogEntry
from models.links.entity_link import EntityLink


def _mentions(session: Session, entity_type: str, entity_id: int) -> set[tuple[str, int]]:
    return {
        link.other_side(entity_type, entity_id)
        for link in EntityLink.for_entity(session, entity_type, entity_id)
        if link.relation == "mentions"
    }


def test_log_entry_body_links_and_unlinks_references(db_session: Session) -> None:
    todo = make_todo(db_session, "t")
    entry = LogEntry.create(db_session, f"Finished Todo:{todo.id}", inbox(db_session))
    db_session.commit()
    assert _mentions(db_session, "LogEntry", entry.id) == {("Todo", todo.id)}

    entry.body = "No reference any more"
    db_session.commit()
    assert _mentions(db_session, "LogEntry", entry.id) == set()
