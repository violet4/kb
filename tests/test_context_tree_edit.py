"""Creating and re-parenting contexts: Context.create/move_under, and the API routes over them."""

from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.contexts_router import router
from models.base import Base
from api.deps import get_session
from context import PlacementError, place
from models.context import Context, Tag
from models.knowledge.log_entry import LogEntry
from conftest import make_todo


@pytest.fixture
def client() -> Iterator[TestClient]:
    # FastAPI runs sync routes on a worker thread, so the in-memory database must be one
    # shared connection usable from any thread.
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def session() -> Iterator[Session]:
        with factory() as s:
            yield s

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = session
    yield TestClient(app)


def test_create_refuses_duplicate_name(db_session: Session) -> None:
    Context.create(db_session, "home")
    with pytest.raises(ValueError, match="already exists"):
        Context.create(db_session, "home")


def test_move_under_refuses_cycle(db_session: Session) -> None:
    home = Context.create(db_session, "home")
    kitchen = Context.create(db_session, "kitchen", parent=home)
    pantry = Context.create(db_session, "pantry", parent=kitchen)
    with pytest.raises(ValueError, match="own descendant"):
        home.move_under(pantry)
    with pytest.raises(ValueError, match="own descendant"):
        home.move_under(home)
    pantry.move_under(None)
    assert pantry.parent is None


def test_api_create_and_move(client: TestClient, db_session: Session) -> None:
    home = client.post("/contexts", json={"name": "home"}).json()
    kitchen = client.post("/contexts", json={"name": "kitchen", "parent_id": home["id"]}).json()
    assert kitchen["parent_id"] == home["id"]

    assert client.post("/contexts", json={"name": "home"}).status_code == 409
    assert client.put(f"/contexts/{home['id']}/parent", json={"parent_id": kitchen["id"]}).status_code == 409
    assert client.put(f"/contexts/{home['id']}/parent", json={"parent_id": 9999}).status_code == 400

    moved = client.put(f"/contexts/{kitchen['id']}/parent", json={"parent_id": None}).json()
    assert moved["parent_id"] is None


def test_place_moves_between_context_and_tag(db_session: Session) -> None:
    home = Context.create(db_session, "home")
    tavern = Tag(name="tavern")
    db_session.add(tavern)
    todo = make_todo(db_session, "buy salt")
    place(todo, tag=tavern)
    assert (todo.context, todo.tag) == (None, tavern)
    place(todo, context=home)
    assert (todo.context, todo.tag) == (home, None)
    with pytest.raises(PlacementError, match="must have a context"):
        place(todo)


def test_place_refuses_tag_for_context_only_row(db_session: Session) -> None:
    entry = LogEntry.create(db_session, "it rained", context=Context.create(db_session, "home"))
    tavern = Tag(name="tavern")
    db_session.add(tavern)
    with pytest.raises(PlacementError, match="needs a context"):
        place(entry, tag=tavern)
