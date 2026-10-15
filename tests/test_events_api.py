"""POST /events: an event is created in the context or on the tag the request names, and a
request naming neither is refused rather than failing the database's context-or-tag CHECK."""

from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.deps import get_session
from api.events_router import router
from conftest import inbox
from models.base import Base
from models.context import Tag

EVENT = {"title": "dentist", "starts_at": "2026-10-22T16:00:00Z"}


@pytest.fixture
def db() -> Iterator[tuple[TestClient, Session]]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def session() -> Iterator[Session]:
        with factory() as s:
            yield s

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = session
    with factory() as s:
        yield TestClient(app), s


def test_create_in_a_context(db: tuple[TestClient, Session]) -> None:
    client, s = db
    context = inbox(s)
    s.commit()
    response = client.post("/events", json={**EVENT, "context_id": context.id})
    assert response.status_code == 200
    assert response.json()["context_name"] == "inbox"


def test_create_on_a_tag(db: tuple[TestClient, Session]) -> None:
    client, s = db
    tag = Tag(name="tavern")
    s.add(tag)
    s.commit()
    response = client.post("/events", json={**EVENT, "tag_id": tag.id})
    assert response.status_code == 200
    assert response.json()["tag_name"] == "tavern"


def test_create_without_a_placement_is_refused(db: tuple[TestClient, Session]) -> None:
    client, _ = db
    assert client.post("/events", json=EVENT).status_code == 400
