"""The SQLite engine, its per-connection setup, and the session factory."""

from __future__ import annotations

import sqlite_vec  # type: ignore[import-untyped]  # no type stubs published for this package
from sqlalchemy import create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from models.base import Base
from schema_version import DB_PATH

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def load_sqlite_vec(conn: DBAPIConnection, _: ConnectionPoolEntry | None = None) -> None:
    """Load sqlite-vec (vec_distance_cosine, used by HasEmbedding.search) into a new connection.
    A "connect" listener for any engine kb searches, the test fixtures' included."""
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


@event.listens_for(_engine, "connect")
def _set_pragma(conn: DBAPIConnection, record: ConnectionPoolEntry) -> None:
    load_sqlite_vec(conn, record)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")


SessionFactory = sessionmaker(bind=_engine)


def init_db() -> None:
    """Create tables for a fresh database. Use alembic for schema changes on existing DBs."""
    Base.metadata.create_all(_engine)
