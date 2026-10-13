"""Daily, a recurring item."""

from __future__ import annotations

import enum
from datetime import date, datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from models.base import Base, _now
from models.behaviors.embedding import HasEmbedding
from models.behaviors.placement import HasContextOrTag
from models.context import Context, Tag
from models.journal.tracking import HasJournal
from models.settings import Settings


class DailyTier(enum.Enum):
    CRITICAL = "critical"  # always surfaces in summary until completed today
    OPTIONAL = "optional"  # hidden by default, needs an explicit request (e.g. kb daily list --all)


class Daily(Base, HasContextOrTag, HasEmbedding, HasJournal):
    """A recurring/optional item — distinct from Goal (a purpose/end-state) and Todo (a step toward one).

    domain ("irl"/"pg", mirrors Vendor.domain) separates life-maintenance dailies from game dailies.
    tier controls default summary visibility: CRITICAL always surfaces until completed today,
    OPTIONAL stays hidden unless explicitly requested.

    recurrence is a required cadence rule (grammar below) -- every Daily has one, so completing it
    always computes and stores next_due_date, making "is this due" a plain date comparison
    rather than recomputed day-boundary math. next_due_date is the single source of truth for when
    a Daily is next due; there is no separate "last completed" record, since only the upcoming due
    date is ever queried, not completion history.

    next_due_date is a calendar date, not a timestamp -- a Daily's due-ness is a day-cycle question
    ("which day-boundary window is this due in"), never a sub-day one, so the field only ever needs
    to answer "is today's day-cycle at or past this date." day_boundary_hour/timezone convert
    "now" to a day-cycle date once, via _current_day(); nothing downstream needs an instant.

    Recurrence grammar:
      "daily"        -- due again at the next day-boundary after completion.
      "every:N"      -- due again N days after completion (e.g. "every:2" for alternating-day items).
      "weekly:DAY"   -- due again on the next occurrence of DAY ("MON".."SUN") after completion.
      "monthly:D"    -- due again on day D of the next applicable month after completion (D 1-28).
      "yearly:MM-DD" -- due again on month MM day DD of the next applicable year after completion
                        (e.g. "yearly:07-23" for a July 23 birthday/anniversary).

    show_after_hour (0-23, local time) is applied after next_due_date decides a Daily is due "today"
    -- it further hides a Daily that's due today (but not yet overdue) from due()/summary until
    that local hour, so evening-only items (e.g. "shower before bed") don't clutter the morning
    view. Once overdue (next_due_date has fully passed), show_after_hour no longer applies.

    remind_days_before (default 0) widens visibility to start that many days ahead of
    next_due_date -- for a yearly reminder (e.g. a birthday) that needs advance notice to be
    actionable (buy a gift, plan a call), not just same-day visibility. It only affects when a
    Daily first becomes visible; is_overdue/complete/catch_up stay anchored on next_due_date,
    unaffected. show_after_hour does not apply inside the lead-in window (an hour-of-day gate
    doesn't compose meaningfully across multiple days) -- it only gates on the due day itself.
    """

    __tablename__ = "daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    context_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("context.id"), nullable=True)
    domain: Mapped[str] = mapped_column(String, nullable=False, default="irl")
    tier: Mapped[DailyTier] = mapped_column(
        Enum(DailyTier, create_constraint=True, validate_strings=True), nullable=False, default=DailyTier.CRITICAL
    )
    recurrence: Mapped[str] = mapped_column(String, nullable=False, default="daily")
    show_after_hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    remind_days_before: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    context: Mapped[Optional[Context]] = relationship("Context")
    tag: Mapped[Optional[Tag]] = relationship("Tag")

    @staticmethod
    def _embed_fields() -> set[str]:
        return {"description", "notes"}

    def _embed_source_text(self) -> str:
        return f"{self.description}\n\n{self.notes}" if self.notes else self.description

    _WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

    @classmethod
    def _current_day(cls, session: Session, now: datetime) -> date:
        """Which day-cycle "now" falls in, as a plain date -- computed by applying
        Settings.day_boundary_hour in local time (not UTC), so a late local bedtime
        doesn't get treated as already past a UTC-midnight-adjacent cutoff. This is
        the only place day_boundary_hour/timezone are ever consulted; every other
        Daily method compares dates that are already resolved to day-cycles."""
        settings = Settings.get(session)
        local_now = now.astimezone(settings.resolved_timezone())
        local_day_start = local_now.replace(hour=settings.day_boundary_hour, minute=0, second=0, microsecond=0)
        if local_now < local_day_start:
            local_day_start -= timedelta(days=1)
        return local_day_start.date()

    @classmethod
    def active(
        cls,
        session: Session,
        context: Optional[Context] = None,
        contexts: Optional[Sequence[Context]] = None,
    ) -> Sequence[Daily]:
        """`context` matches that single context exactly; `contexts` (e.g. from
        Context.self_and_descendants) matches any context in the given set, plus any
        Daily whose tag_id is carried by a Context in that set (see HasContextOrTag)."""
        q = select(cls).where(cls.is_active.is_(True), cls.deleted_at.is_(None))
        if context is not None:
            q = q.where(cls.context_id == context.id)
        if contexts is not None:
            matches = cls.matches_contexts(contexts)
            q = q.where(matches)
        return session.scalars(q).all()

    def is_overdue(self, session: Session) -> bool:
        """True once today's day-cycle is past the one this Daily was due in --
        e.g. litter due Monday (and shown from show_after_hour onward) is fine
        through the rest of Monday, then becomes overdue right at Tuesday's
        day-boundary, the moment the day it should have been done in has closed."""
        today = self._current_day(session, _now())
        return today > self.next_due_date

    def is_due_now(self, session: Session) -> bool:
        """True once today's day-cycle has reached next_due_date minus
        remind_days_before (0 by default, i.e. exactly next_due_date), gated by
        show_after_hour (0-23 local) so evening-only items don't surface in the
        morning -- but only on the day it first became due, never inside a
        remind_days_before lead-in window. Once is_overdue() is true the item has
        already missed its day entirely, so show_after_hour no longer applies: an
        overdue "shower before bed" must stay visible all day, not just evenings."""
        today = self._current_day(session, _now())
        window_start = self.next_due_date - timedelta(days=self.remind_days_before)
        if today < window_start:
            return False
        if self.show_after_hour is not None and today == self.next_due_date:
            settings = Settings.get(session)
            local_hour = _now().astimezone(settings.resolved_timezone()).hour
            if local_hour < self.show_after_hour:
                return False
        return True

    @classmethod
    def due(cls, session: Session, domain: Optional[str] = None, tier: Optional[DailyTier] = None) -> list[Daily]:
        """Active dailies currently due, per is_due_now()."""
        q = select(cls).where(cls.is_active.is_(True), cls.deleted_at.is_(None))
        if domain is not None:
            q = q.where(cls.domain == domain)
        if tier is not None:
            q = q.where(cls.tier == tier)
        dailies = session.scalars(q).all()
        return [d for d in dailies if d.is_due_now(session)]

    @classmethod
    def create(
        cls,
        session: Session,
        description: str,
        context: Optional[Context] = None,
        tag: Optional[Tag] = None,
        domain: str = "irl",
        tier: DailyTier = DailyTier.CRITICAL,
        recurrence: str = "daily",
        show_after_hour: Optional[int] = None,
        location: Optional[str] = None,
        remind_days_before: int = 0,
        notes: Optional[str] = None,
    ) -> Daily:
        daily = cls(
            description=description,
            context_id=context.id if context else None,
            tag_id=tag.id if tag else None,
            domain=domain,
            tier=tier,
            recurrence=recurrence,
            show_after_hour=show_after_hour,
            location=location,
            remind_days_before=remind_days_before,
            notes=notes,
        )
        # Seed as due today, not one recurrence step back through _compute_next_due
        # -- that only lands on "already due" for the daily cadence; every:N>1/
        # weekly/monthly would land a full period in the future.
        daily.next_due_date = daily._current_day(session, _now())
        daily.reembed()
        session.add(daily)
        session.flush()
        return daily

    def _compute_next_due(self, session: Session, after: date) -> date:
        """The next due date per this Daily's recurrence rule."""
        kind, _, arg = self.recurrence.partition(":")

        if kind == "daily" or not kind:
            return after + timedelta(days=1)
        elif kind == "every":
            return after + timedelta(days=int(arg))
        elif kind == "weekly":
            target = Daily._WEEKDAYS.index(arg.upper())
            days_ahead = (target - after.weekday()) % 7
            days_ahead = days_ahead or 7
            return after + timedelta(days=days_ahead)
        elif kind == "monthly":
            day = int(arg)
            year, month = after.year, after.month + 1
            if month > 12:
                month = 1
                year += 1
            return after.replace(year=year, month=month, day=day)
        elif kind == "yearly":
            month_str, _, day_str = arg.partition("-")
            month, day = int(month_str), int(day_str)
            year = after.year
            if (month, day) <= (after.month, after.day):
                year += 1
            return date(year, month, day)
        else:
            raise ValueError(f"unknown recurrence kind: {kind!r}")

    def complete(self, session: Session) -> None:
        """Advance next_due_date one recurrence step past the day being completed --
        anchored on next_due_date itself, not on today's date, so completing something
        late (after its day closed) still lands on the very next occurrence rather than
        skipping ahead an extra step because of how late the completion happened."""
        self.next_due_date = self._compute_next_due(session, self.next_due_date)

    def catch_up(self, session: Session) -> None:
        """Advance next_due_date forward through however many missed days have
        elapsed, landing on the first occurrence that isn't overdue -- for a Daily
        that's been neglected for multiple cycles, rather than requiring complete()
        to be called once per missed day."""
        while self.is_overdue(session):
            self.next_due_date = self._compute_next_due(session, self.next_due_date)

    def catch_up_would_stay_due(self, session: Session) -> bool:
        """Whether this Daily would still be is_due_now() immediately after catch_up() --
        true for a short recurrence (e.g. "daily") landing back on today, or a
        remind_days_before lead-in wide enough to already cover the caught-up date. Computed
        without mutating next_due_date, so the frontend can distinguish a Catch Up that clears
        the row from one that leaves it in place under a different due date."""
        next_due_date = self.next_due_date
        while self._current_day(session, _now()) > next_due_date:
            next_due_date = self._compute_next_due(session, next_due_date)
        today = self._current_day(session, _now())
        window_start = next_due_date - timedelta(days=self.remind_days_before)
        if today < window_start:
            return False
        if self.show_after_hour is not None and today == next_due_date:
            settings = Settings.get(session)
            local_hour = _now().astimezone(settings.resolved_timezone()).hour
            if local_hour < self.show_after_hour:
                return False
        return True

    def __repr__(self) -> str:
        return f"<Daily #{self.id} {self.description!r}{self.age_marker()}>"
