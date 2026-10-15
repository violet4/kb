"""Rows a before_flush listener queues for its after_flush counterpart, kept per session.

A new row has no id until its INSERT runs, so work that needs the id (its Journal CREATE row,
its auto-links) is queued before the flush and done after it. The queue lives on the session,
not in a module global: one process serves many sessions, and a flush that fails never
reaches after_flush, so a global queue would keep the id-less row and fail every later flush
in every session. The session's own queue is dropped when it rolls back, which a failed flush
always does.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session, SessionTransaction

_INFO_KEY = "flush_pending"


def queue(session: Session, name: str) -> list[Any]:
    """The named queue for this session's current flush, to append to in before_flush."""
    queues: dict[str, list[Any]] = session.info.setdefault(_INFO_KEY, {})
    return queues.setdefault(name, [])


def take(session: Session, name: str) -> list[Any]:
    """Empties the named queue and returns what it held, for after_flush."""
    queues: dict[str, list[Any]] = session.info.get(_INFO_KEY, {})
    return queues.pop(name, [])


@event.listens_for(Session, "after_soft_rollback")
def _drop_on_rollback(session: Session, previous_transaction: SessionTransaction) -> None:
    session.info.pop(_INFO_KEY, None)
