"""The context page's record listing: every filed type appears (types without a section of
their own under `others`), and each type's own .active() decides what is current, with the
rest listed, marked inactive, only on request."""

from datetime import datetime, timezone
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.contexts_router import router
from api.deps import get_session
from conftest import inbox, make_daily
from models.base import Base
from models.work.event import Event
from models.work.goal import Goal, GoalStatus


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


def test_page_lists_other_filed_types_and_inactive_on_request(db: tuple[TestClient, Session]) -> None:
    client, s = db
    here = inbox(s)
    s.add(Goal(title="dropped goal", context=here, status=GoalStatus.ABANDONED))
    s.add(Event(title="deadline", starts_at=datetime(2027, 4, 15, tzinfo=timezone.utc), context=here))
    make_daily(s, "old routine", context=here).is_active = False
    s.commit()

    page = client.get(f"/contexts/{here.id}").json()
    assert page["goals"] == []
    assert [(r["type"], r["label"], r["inactive"]) for r in page["others"]] == [("Event", "deadline", False)]

    page = client.get(f"/contexts/{here.id}?include_inactive=true").json()
    assert [(g["title"], g["inactive"]) for g in page["goals"]] == [("dropped goal", True)]
    assert [(r["type"], r["inactive"]) for r in page["others"]] == [("Daily", True), ("Event", False)]

    counts = {n["name"]: n["counts"] for n in client.get("/contexts/tree").json()}
    assert counts["inbox"]["other"] == 1  # the current Event; the inactive Daily is not counted
