"""Make Daily.recurrence required, drop last_completed_at

next_due_at is now the single source of truth for "when is this Daily due" --
last_completed_at was a scalar last-write-wins field, never real history, so
dropping it loses nothing that was actually being tracked. Every Daily gets an
explicit recurrence ("daily" by default) so next_due_at is always populated.

Revision ID: 55e747832752
Revises: 244479b916a4
Create Date: 2026-07-08 13:42:24.835221

"""

from pathlib import Path
from typing import Sequence, Union
from zoneinfo import ZoneInfo

from datetime import datetime, timedelta, timezone as dt_timezone

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "55e747832752"
down_revision: Union[str, Sequence[str], None] = "244479b916a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _resolved_timezone(tz_override: str | None) -> ZoneInfo:
    if tz_override:
        return ZoneInfo(tz_override)
    localtime = Path("/etc/localtime")
    if localtime.is_symlink():
        target = str(localtime.resolve())
        marker = "zoneinfo/"
        if marker in target:
            return ZoneInfo(target.split(marker, 1)[1])
    return ZoneInfo("UTC")


def _compute_next_due(recurrence: str, after: datetime, day_boundary_hour: int, tz: ZoneInfo) -> datetime:
    """Mirrors Daily._compute_next_due -- duplicated here since migrations must not
    import live model code (models.py can change shape after this migration is written)."""
    local_after = after.astimezone(tz)
    kind, _, arg = recurrence.partition(":")

    if kind == "daily" or not kind:
        local_next = local_after + timedelta(days=1)
    elif kind == "every":
        local_next = local_after + timedelta(days=int(arg))
    elif kind == "weekly":
        target = _WEEKDAYS.index(arg.upper())
        days_ahead = (target - local_after.weekday()) % 7
        days_ahead = days_ahead or 7
        local_next = local_after + timedelta(days=days_ahead)
    elif kind == "monthly":
        day = int(arg)
        year, month = local_after.year, local_after.month + 1
        if month > 12:
            month = 1
            year += 1
        local_next = local_after.replace(year=year, month=month, day=day)
    else:
        raise ValueError(f"unknown recurrence kind: {kind!r}")

    local_next = local_next.replace(hour=day_boundary_hour, minute=0, second=0, microsecond=0)
    return local_next.astimezone(dt_timezone.utc)


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    settings_row = conn.execute(sa.text("select day_boundary_hour, timezone from settings where id = 1")).one_or_none()
    day_boundary_hour = settings_row[0] if settings_row else 4
    tz = _resolved_timezone(settings_row[1] if settings_row else None)

    rows = conn.execute(sa.text("select id, recurrence, next_due_at, last_completed_at from daily")).all()
    for row in rows:
        recurrence = row.recurrence or "daily"
        if row.next_due_at is not None:
            next_due_at = (
                row.next_due_at if isinstance(row.next_due_at, datetime) else datetime.fromisoformat(row.next_due_at)
            )
            if next_due_at.tzinfo is None:
                next_due_at = next_due_at.replace(tzinfo=dt_timezone.utc)
        else:
            if row.last_completed_at is not None:
                reference = (
                    row.last_completed_at
                    if isinstance(row.last_completed_at, datetime)
                    else datetime.fromisoformat(row.last_completed_at)
                )
                if reference.tzinfo is None:
                    reference = reference.replace(tzinfo=dt_timezone.utc)
            else:
                reference = datetime.now(dt_timezone.utc) - timedelta(days=1)
            next_due_at = _compute_next_due(recurrence, reference, day_boundary_hour, tz)
        conn.execute(
            sa.text("update daily set recurrence = :recurrence, next_due_at = :next_due_at where id = :id"),
            {"recurrence": recurrence, "next_due_at": next_due_at, "id": row.id},
        )

    with op.batch_alter_table("daily", schema=None) as batch_op:
        batch_op.alter_column("recurrence", existing_type=sa.VARCHAR(), nullable=False)
        batch_op.alter_column("next_due_at", existing_type=sa.DATETIME(), nullable=False)
        batch_op.drop_column("last_completed_at")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("daily", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_completed_at", sa.DATETIME(), nullable=True))
        batch_op.alter_column("next_due_at", existing_type=sa.DATETIME(), nullable=True)
        batch_op.alter_column("recurrence", existing_type=sa.VARCHAR(), nullable=True)
