"""Shared FastAPI dependencies -- one Session-per-request generator, matching
synth's own `_get_session` pattern (see patches_router.py)."""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from models import SessionFactory


def get_session() -> Iterator[Session]:
    with SessionFactory() as session:
        yield session
