"""Daily recurrence behavior: due()/complete() across the day-boundary and every
recurrence grammar (daily, every:N, weekly:DAY, monthly:D), using time_machine to
control "now" deterministically instead of waiting on real calendar days. recurrence
defaults to "daily" when unspecified, so cases exercising the default overlap with
explicit "daily" cases but confirm the default itself behaves the same way.
"""

from datetime import date, datetime, timedelta, timezone

import time_machine
from sqlalchemy.orm import Session

from models import Daily, DailyTier, Settings


def _set_utc_boundary(session: Session, hour: int = 4) -> None:
    """Pin Settings to a fixed, deterministic day-boundary in UTC, so test behavior
    doesn't depend on the host machine's /etc/localtime."""
    settings = Settings.get(session)
    settings.day_boundary_hour = hour
    settings.timezone = "UTC"
    session.commit()


def test_default_recurrence_due_immediately_after_creation(db_session: Session) -> None:
    _set_utc_boundary(db_session)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "water plants")
        db_session.commit()
        assert daily in Daily.due(db_session)


def test_default_recurrence_not_due_same_day_after_completion(db_session: Session) -> None:
    _set_utc_boundary(db_session)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)) as traveller:
        daily = Daily.create(db_session, "water plants")
        daily.complete(db_session)
        db_session.commit()
        assert daily not in Daily.due(db_session)

        traveller.shift(timedelta(hours=3))
        assert daily not in Daily.due(db_session)


def test_default_recurrence_due_again_after_day_boundary(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)) as traveller:
        daily = Daily.create(db_session, "water plants")
        daily.complete(db_session)
        db_session.commit()

        # Still the same day-window (before the next 04:00 boundary).
        traveller.move_to(datetime(2026, 1, 2, 3, 59, tzinfo=timezone.utc))
        assert daily not in Daily.due(db_session)

        # Past the boundary -- a new day-window has started.
        traveller.move_to(datetime(2026, 1, 2, 4, 1, tzinfo=timezone.utc))
        assert daily in Daily.due(db_session)


def test_recurrence_daily_explicit_matches_default(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)) as traveller:
        daily = Daily.create(db_session, "stretch", recurrence="daily")
        daily.complete(db_session)
        db_session.commit()
        assert daily.next_due_date == date(2026, 1, 2)
        assert daily not in Daily.due(db_session)

        traveller.move_to(datetime(2026, 1, 2, 4, 1, tzinfo=timezone.utc))
        assert daily in Daily.due(db_session)


def test_recurrence_every_n_days(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)) as traveller:
        daily = Daily.create(db_session, "alternate-day chore", recurrence="every:2")
        daily.complete(db_session)
        db_session.commit()
        assert daily.next_due_date == date(2026, 1, 3)

        traveller.move_to(datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc))
        assert daily not in Daily.due(db_session)

        traveller.move_to(datetime(2026, 1, 3, 4, 1, tzinfo=timezone.utc))
        assert daily in Daily.due(db_session)


def test_recurrence_weekly_lands_on_target_weekday(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    # 2026-01-01 is a Thursday.
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)) as traveller:
        daily = Daily.create(db_session, "take out recycling", recurrence="weekly:WED")
        daily.complete(db_session)
        db_session.commit()
        # Next Wednesday after Thursday 2026-01-01 is 2026-01-07.
        assert daily.next_due_date == date(2026, 1, 7)

        traveller.move_to(datetime(2026, 1, 7, 3, 59, tzinfo=timezone.utc))
        assert daily not in Daily.due(db_session)

        traveller.move_to(datetime(2026, 1, 7, 4, 1, tzinfo=timezone.utc))
        assert daily in Daily.due(db_session)


def test_recurrence_weekly_on_completion_weekday_waits_a_full_week(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    # 2026-01-01 is a Thursday; completing on Thursday with recurrence weekly:THU
    # should land a week later, not the same day.
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "weekly on same day", recurrence="weekly:THU")
        daily.complete(db_session)
        db_session.commit()
        assert daily.next_due_date == date(2026, 1, 8)


def test_recurrence_monthly_lands_on_target_day_next_month(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)) as traveller:
        daily = Daily.create(db_session, "pay rent", recurrence="monthly:1")
        daily.complete(db_session)
        db_session.commit()
        assert daily.next_due_date == date(2026, 2, 1)

        traveller.move_to(datetime(2026, 1, 31, 23, 59, tzinfo=timezone.utc))
        assert daily not in Daily.due(db_session)

        traveller.move_to(datetime(2026, 2, 1, 4, 1, tzinfo=timezone.utc))
        assert daily in Daily.due(db_session)


def test_recurrence_monthly_rolls_over_year_boundary(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 12, 10, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "december chore", recurrence="monthly:15")
        daily.complete(db_session)
        db_session.commit()
        assert daily.next_due_date == date(2027, 1, 15)


def test_recurrence_yearly_lands_on_target_date_next_year(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "gf's HRT anniversary", recurrence="yearly:07-23")
        daily.complete(db_session)
        db_session.commit()
        assert daily.next_due_date == date(2027, 7, 23)


def test_recurrence_yearly_before_target_date_lands_this_year(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "gf's HRT anniversary", recurrence="yearly:07-23")
        daily.complete(db_session)
        db_session.commit()
        assert daily.next_due_date == date(2026, 7, 23)


def test_due_filters_by_domain_and_tier(db_session: Session) -> None:
    _set_utc_boundary(db_session)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)):
        irl_critical = Daily.create(db_session, "irl critical", domain="irl", tier=DailyTier.CRITICAL)
        irl_optional = Daily.create(db_session, "irl optional", domain="irl", tier=DailyTier.OPTIONAL)
        pg_daily = Daily.create(db_session, "pg daily", domain="pg")
        db_session.commit()

        assert Daily.due(db_session, domain="irl") == [irl_critical, irl_optional]
        assert Daily.due(db_session, domain="irl", tier=DailyTier.CRITICAL) == [irl_critical]
        assert Daily.due(db_session, domain="pg") == [pg_daily]


def test_is_overdue_flips_a_full_day_after_becoming_due(db_session: Session) -> None:
    """A Daily that becomes due at next_due_date gets the rest of that day to be
    done -- not yet overdue at the exact instant it becomes due, nor for the rest of
    that day. Only once the *following* day-boundary passes with it still not
    completed does it flip to overdue -- e.g. litter due Tuesday is fine all through
    Tuesday, then overdue from Wednesday's day-boundary onward until completed."""
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 5, 12, 26, tzinfo=timezone.utc)) as traveller:
        daily = Daily.create(db_session, "litter")
        daily.complete(db_session)
        db_session.commit()
        assert daily.next_due_date == date(2026, 1, 6)

        # The instant it becomes due: due, but not yet overdue -- gets the rest of today.
        traveller.move_to(datetime(2026, 1, 6, 4, 0, tzinfo=timezone.utc))
        assert not daily.is_overdue(db_session)

        # Later the same day: still due today, still not overdue.
        traveller.move_to(datetime(2026, 1, 6, 23, 0, tzinfo=timezone.utc))
        assert not daily.is_overdue(db_session)

        # Just before the next day-boundary: still not overdue.
        traveller.move_to(datetime(2026, 1, 7, 3, 59, tzinfo=timezone.utc))
        assert not daily.is_overdue(db_session)

        # At the following boundary: overdue, since the due-day ended uncompleted.
        traveller.move_to(datetime(2026, 1, 7, 4, 0, tzinfo=timezone.utc))
        assert daily.is_overdue(db_session)

        # Stays overdue afterward.
        traveller.move_to(datetime(2026, 1, 7, 5, 0, tzinfo=timezone.utc))
        assert daily.is_overdue(db_session)


def test_is_overdue_false_immediately_after_completion(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "litter")
        daily.complete(db_session)
        db_session.commit()
        assert not daily.is_overdue(db_session)


def test_show_after_hour_hides_until_hour_on_due_day_but_not_once_overdue(db_session: Session) -> None:
    """show_after_hour (e.g. an evening-only "shower before bed" item) should hide
    the Daily until that local hour on the day it becomes due, but must stop gating
    once the item is actually overdue -- an overdue evening item still needs to show
    up in the morning, not stay hidden until yet another evening arrives."""
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)) as traveller:
        daily = Daily.create(db_session, "shower before bed", show_after_hour=19)
        daily.complete(db_session)
        db_session.commit()
        assert daily.next_due_date == date(2026, 1, 6)

        # Due day, before show_after_hour: due but hidden.
        traveller.move_to(datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc))
        assert not daily.is_overdue(db_session)
        assert not daily.is_due_now(db_session)

        # Due day, at/after show_after_hour: now shown.
        traveller.move_to(datetime(2026, 1, 6, 19, 0, tzinfo=timezone.utc))
        assert not daily.is_overdue(db_session)
        assert daily.is_due_now(db_session)

        # Next day-boundary passes uncompleted: overdue -- must show even before
        # show_after_hour, since the day it should've been done on is fully closed.
        traveller.move_to(datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc))
        assert daily.is_overdue(db_session)
        assert daily.is_due_now(db_session)


def test_inactive_daily_never_due(db_session: Session) -> None:
    _set_utc_boundary(db_session)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "retired chore")
        daily.is_active = False
        db_session.commit()
        assert daily not in Daily.due(db_session)


def test_every_n_days_due_immediately_after_creation(db_session: Session) -> None:
    """create() must seed next_due_date as today, not one recurrence step ahead --
    every:2/weekly/monthly dailies used to only become due a full cadence after
    creation instead of right away, unlike the default "daily" case."""
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "alternate-day chore", recurrence="every:2")
        db_session.commit()
        assert daily in Daily.due(db_session)


def test_weekly_due_immediately_after_creation(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "take out recycling", recurrence="weekly:WED")
        db_session.commit()
        assert daily in Daily.due(db_session)


def test_monthly_due_immediately_after_creation(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "pay rent", recurrence="monthly:1")
        db_session.commit()
        assert daily in Daily.due(db_session)


def test_complete_late_advances_only_one_window(db_session: Session) -> None:
    """Completing a Daily well after its window closed (e.g. finishing yesterday's
    litter this afternoon) must land on the very next occurrence, anchored on
    next_due_date -- not skip an extra step because of how late "now" is when
    complete() is called."""
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "litter")
        db_session.commit()
        assert daily.next_due_date == date(2026, 1, 5)

    # Two full day-windows pass uncompleted -- now overdue -- before it's completed.
    with time_machine.travel(datetime(2026, 1, 7, 14, 0, tzinfo=timezone.utc)):
        assert daily.is_overdue(db_session)
        daily.complete(db_session)
        db_session.commit()
        # Anchored on the missed next_due_date (Jan 5), not on "now" (Jan 7) --
        # lands on Jan 6, the very next occurrence, not Jan 8.
        assert daily.next_due_date == date(2026, 1, 6)


def test_catch_up_advances_through_multiple_missed_windows(db_session: Session) -> None:
    """A weekly Daily neglected for three weeks needs catch_up() to land on the
    next non-overdue occurrence in one call, instead of requiring complete() to be
    called once per missed window."""
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)):
        # 2026-01-01 is a Thursday.
        daily = Daily.create(db_session, "take out recycling", recurrence="weekly:WED")
        db_session.commit()

    with time_machine.travel(datetime(2026, 1, 22, 12, 0, tzinfo=timezone.utc)):
        assert daily.is_overdue(db_session)
        daily.catch_up(db_session)
        db_session.commit()
        assert daily.next_due_date == date(2026, 1, 28)
        assert not daily.is_overdue(db_session)


def test_catch_up_no_op_when_not_overdue(db_session: Session) -> None:
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)):
        daily = Daily.create(db_session, "litter")
        db_session.commit()
        before = daily.next_due_date
        daily.catch_up(db_session)
        assert daily.next_due_date == before


def test_remind_days_before_surfaces_ahead_of_next_due_date(db_session: Session) -> None:
    """A yearly Daily (e.g. a birthday) with remind_days_before=7 should become
    due 7 days ahead of next_due_date, not only on the day itself -- so it's
    actionable (buy a gift, plan a call) with real lead time."""
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)) as traveller:
        # Created on the anniversary date itself, matching how create() seeds
        # next_due_date as today (see test_recurrence_yearly_* for the same pattern).
        daily = Daily.create(db_session, "Deb's birthday", recurrence="yearly:09-16", remind_days_before=7)
        db_session.commit()
        assert daily.next_due_date == date(2026, 9, 16)

        # 8 days before: not yet due.
        traveller.move_to(datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        assert not daily.is_due_now(db_session)

        # Exactly 7 days before (the lead-in boundary itself): due.
        traveller.move_to(datetime(2026, 9, 9, 4, 1, tzinfo=timezone.utc))
        assert daily.is_due_now(db_session)

        # On the day itself: still due.
        traveller.move_to(datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc))
        assert daily.is_due_now(db_session)


def test_remind_days_before_default_matches_exact_day_only_behavior(db_session: Session) -> None:
    """remind_days_before defaults to 0 -- a plain Daily with no lead-in configured
    must behave exactly as before this feature existed: due only from next_due_date
    onward, not a day earlier."""
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)) as traveller:
        daily = Daily.create(db_session, "water plants")
        db_session.commit()
        assert daily.remind_days_before == 0

        traveller.move_to(datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc))
        assert not daily.is_due_now(db_session)

        traveller.move_to(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))
        assert daily.is_due_now(db_session)


def test_remind_days_before_does_not_affect_is_overdue(db_session: Session) -> None:
    """The lead-in window only widens when a Daily first becomes visible -- it must
    not change when a Daily flips to overdue, which stays anchored on next_due_date
    exactly as before."""
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2025, 9, 16, 12, 0, tzinfo=timezone.utc)) as traveller:
        daily = Daily.create(db_session, "Deb's birthday", recurrence="yearly:09-16", remind_days_before=7)
        daily.complete(db_session)
        db_session.commit()
        assert daily.next_due_date == date(2026, 9, 16)

        # Within the lead-in window, due but not overdue.
        traveller.move_to(datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc))
        assert daily.is_due_now(db_session)
        assert not daily.is_overdue(db_session)

        # On next_due_date itself: still not overdue (same rule as any other Daily).
        traveller.move_to(datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc))
        assert not daily.is_overdue(db_session)

        # Day after next_due_date's boundary passes uncompleted: overdue, same
        # timing as a Daily with no lead-in at all.
        traveller.move_to(datetime(2026, 9, 17, 4, 1, tzinfo=timezone.utc))
        assert daily.is_overdue(db_session)


def test_remind_days_before_ignores_show_after_hour(db_session: Session) -> None:
    """show_after_hour only gates same-day visibility on the exact due date --
    it must not apply inside a multi-day remind_days_before lead-in window, since
    an hour-of-day gate doesn't compose meaningfully across multiple days."""
    _set_utc_boundary(db_session, hour=4)
    with time_machine.travel(datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)) as traveller:
        daily = Daily.create(
            db_session,
            "Deb's birthday",
            recurrence="yearly:09-16",
            remind_days_before=7,
            show_after_hour=19,
        )
        db_session.commit()

        # Within the lead-in window, before show_after_hour local-time: still due,
        # since show_after_hour doesn't apply here.
        traveller.move_to(datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc))
        assert daily.is_due_now(db_session)

        # On the due day itself, before show_after_hour: show_after_hour applies
        # exactly as it does for any other Daily on its due day.
        traveller.move_to(datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc))
        assert not daily.is_due_now(db_session)

        traveller.move_to(datetime(2026, 9, 16, 19, 0, tzinfo=timezone.utc))
        assert daily.is_due_now(db_session)
