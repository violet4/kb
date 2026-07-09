"""convert daily next_due_at to next_due_date

next_due_at stored a UTC instant snapped to day_boundary_hour, but every consumer
only ever asked "which day-cycle is this due in" -- a plain date comparison, never
a sub-day one (show_after_hour already handles the one genuinely time-of-day-
sensitive question, independently). Storing an instant made every read reconstruct
the day-cycle via day-boundary/timezone math (_day_start); storing the date
directly instead means only this migration's backfill needs to do that
reconstruction, once, at conversion time.

Revision ID: a48596724dd0
Revises: 219c80eac979
Create Date: 2026-07-09 14:35:30.956129

"""

from typing import Sequence, Union
from datetime import date, datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a48596724dd0"
down_revision: Union[str, Sequence[str], None] = "219c80eac979"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _resolved_timezone(tz_name: str | None) -> ZoneInfo:
    if tz_name:
        return ZoneInfo(tz_name)
    localtime = Path("/etc/localtime")
    if localtime.is_symlink():
        target = str(localtime.resolve())
        marker = "zoneinfo/"
        if marker in target:
            return ZoneInfo(target.split(marker, 1)[1])
    return ZoneInfo("UTC")


def _current_day(instant: datetime, day_boundary_hour: int, tz: ZoneInfo) -> date:
    local = instant.astimezone(tz)
    local_day_start = local.replace(hour=day_boundary_hour, minute=0, second=0, microsecond=0)
    if local < local_day_start:
        local_day_start -= timedelta(days=1)
    return local_day_start.date()


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    with op.batch_alter_table("daily", schema=None) as batch_op:
        batch_op.add_column(sa.Column("next_due_date", sa.Date(), nullable=True))

    settings_row = conn.execute(sa.text("select day_boundary_hour, timezone from settings where id = 1")).one_or_none()
    day_boundary_hour = settings_row.day_boundary_hour if settings_row else 4
    tz = _resolved_timezone(settings_row.timezone if settings_row else None)

    rows = conn.execute(sa.text("select id, next_due_at from daily")).all()
    for row in rows:
        next_due_at = (
            row.next_due_at if isinstance(row.next_due_at, datetime) else datetime.fromisoformat(row.next_due_at)
        )
        if next_due_at.tzinfo is None:
            next_due_at = next_due_at.replace(tzinfo=dt_timezone.utc)
        next_due_date = _current_day(next_due_at, day_boundary_hour, tz)
        conn.execute(
            sa.text("update daily set next_due_date = :next_due_date where id = :id"),
            {"next_due_date": next_due_date.isoformat(), "id": row.id},
        )

    with op.batch_alter_table("daily", schema=None) as batch_op:
        batch_op.alter_column("next_due_date", existing_type=sa.Date(), nullable=False)
        batch_op.drop_column("next_due_at")


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()

    with op.batch_alter_table("daily", schema=None) as batch_op:
        batch_op.add_column(sa.Column("next_due_at", sa.DATETIME(), nullable=True))

    settings_row = conn.execute(sa.text("select day_boundary_hour from settings where id = 1")).one_or_none()
    day_boundary_hour = settings_row.day_boundary_hour if settings_row else 4

    rows = conn.execute(sa.text("select id, next_due_date from daily")).all()
    for row in rows:
        next_due_date = row.next_due_date if isinstance(row.next_due_date, str) else row.next_due_date.isoformat()
        next_due_at = datetime.fromisoformat(next_due_date).replace(
            hour=day_boundary_hour, minute=0, second=0, microsecond=0, tzinfo=dt_timezone.utc
        )
        conn.execute(
            sa.text("update daily set next_due_at = :next_due_at where id = :id"),
            {"next_due_at": next_due_at.isoformat(), "id": row.id},
        )

    with op.batch_alter_table("daily", schema=None) as batch_op:
        batch_op.alter_column("next_due_at", existing_type=sa.DATETIME(), nullable=False)
        batch_op.drop_column("next_due_date")
