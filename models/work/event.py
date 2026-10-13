"""Event, a dated fact with no status."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base, UtcDateTime, _now
from models.behaviors.embedding import HasEmbedding
from models.behaviors.placement import HasContextOrTag
from models.context import Context, Tag
from models.journal.tracking import HasJournal


class Event(Base, HasContextOrTag, HasEmbedding, HasJournal):
    """A dated occurrence -- distinct from Daily (recurring actionable chore with completion
    state), Todo (committed next-action work), and LogEntry (a fact about the past). An Event
    is a fact pinned to a date/time with no status: a game release, an anniversary, an
    appointment. See kb Idea #13 for the motivating gap (these were previously shoehorned into
    Todo with an ad hoc due-date-like title).

    starts_at is always a full UTC instant (a UtcDateTime column, see base.py). is_all_day
    marks a date-only event (an anniversary, a release day) where starts_at's time-of-day
    component is not meaningful -- stored as midnight UTC and never displayed with a clock time,
    rather than adding a separate Date-typed column: one instant column keeps every event
    orderable/comparable the same way, and is_all_day is the one flag that decides whether the
    time-of-day is shown.

    recurrence, when set, is an RFC 5545 RRULE string (e.g. "FREQ=YEARLY;BYMONTH=7;BYMONTHDAY=23"
    for a July 23 anniversary, or "FREQ=WEEKLY;BYDAY=MO,WE,FR" for a 3x/week appointment) --
    expanded via dateutil.rrule.rrulestr(recurrence, dtstart=starts_at), not a hand-rolled
    grammar. Unlike Daily.recurrence (a small, page-sized set of cadences, exempted under kb
    engineering's own "small grammar is fine hand-rolled" rule), an Event's recurrence has no
    fixed small vocabulary -- BYDAY/BYSETPOS/BYMONTH/interval/count/until compose freely, which
    is exactly the shape engineering's root body asks to check against a battle-tested library
    for before hand-rolling. Null recurrence means a one-off event (e.g. a specific game's 1.0
    release date). next_occurrence() is the one place dateutil is invoked, confining the
    dependency to a single thin layer per kb engineering's third-party-library-boundary rule.

    No completion/status field -- an Event isn't actionable work, it's a fact. A recurring
    Event (a birthday) never gets "completed"; only its next_occurrence() moves forward as time
    passes, purely a computed read, never persisted."""

    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    is_all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurrence: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False, default=_now, onupdate=_now)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional[Tag]] = relationship("Tag")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"title", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.title}\n\n{self.notes}" if self.notes else self.title

    @classmethod
    def active(
        cls,
        session: Session,
        context: Optional[Context] = None,
        contexts: Optional[Sequence[Context]] = None,
    ) -> Sequence[Event]:
        """`context` matches that single context exactly; `contexts` (e.g. from
        Context.self_and_descendants) matches any context in the given set, plus any Event
        whose tag_id is carried by a Context in that set (see HasContextOrTag)."""
        q = select(cls).where(cls.deleted_at.is_(None))
        if context is not None:
            q = q.where(cls.context_id == context.id)
        if contexts is not None:
            matches = cls.matches_contexts(contexts)
            q = q.where(matches)
        return session.scalars(q).all()

    @classmethod
    def create(
        cls,
        session: Session,
        title: str,
        starts_at: datetime,
        context: Optional[Context] = None,
        tag: Optional[Tag] = None,
        is_all_day: bool = False,
        recurrence: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Event:
        event_row = cls(
            title=title,
            starts_at=starts_at,
            is_all_day=is_all_day,
            recurrence=recurrence,
            context_id=context.id if context else None,
            tag_id=tag.id if tag else None,
            notes=notes,
        )
        event_row.reembed()
        session.add(event_row)
        session.flush()
        return event_row

    def next_occurrence(self, after: Optional[datetime] = None) -> Optional[datetime]:
        """The next instant this Event lands on, at or after `after` (default: now) -- the
        event's own starts_at itself if it's still upcoming and non-recurring or hasn't started
        recurring yet, otherwise the first RRULE-generated occurrence at or after `after`. None
        once a non-recurring Event's starts_at is fully in the past. The one call site for
        dateutil.rrule in this codebase -- see class docstring."""
        from dateutil.rrule import rrulestr

        after = after or _now()
        starts_at = self.starts_at
        if not self.recurrence:
            return starts_at if starts_at >= after else None
        rule = rrulestr(self.recurrence, dtstart=starts_at)
        occurrence: Optional[datetime] = rule.after(after, inc=True)
        return occurrence

    def occurrences_between(self, range_start: datetime, range_end: datetime) -> list[datetime]:
        """Every instant this Event lands on within [range_start, range_end) -- the
        week/month calendar-grid view's equivalent of next_occurrence's single-instant
        answer. A non-recurring Event contributes at most its own starts_at; a recurring
        one is expanded via dateutil.rrule.rrulestr.between, still the one place this
        class touches dateutil (see class docstring)."""
        from dateutil.rrule import rrulestr

        starts_at = self.starts_at
        if not self.recurrence:
            return [starts_at] if range_start <= starts_at < range_end else []
        rule = rrulestr(self.recurrence, dtstart=starts_at)
        occurrences: list[datetime] = rule.between(range_start, range_end, inc=True)
        return [occ for occ in occurrences if occ < range_end]

    def __repr__(self) -> str:
        return f"<Event #{self.id} {self.title!r}{self.age_marker()}>"
