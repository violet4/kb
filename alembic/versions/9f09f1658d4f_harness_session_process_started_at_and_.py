"""harness_session process_started_at and ended_at

Revision ID: 9f09f1658d4f
Revises: c71d2f8a9e35
Create Date: 2026-10-12 15:59:30.170983

"""
from datetime import datetime, timezone
from typing import Sequence, Union

import psutil
import sqlalchemy as sa
from alembic import op

from models.base import UtcDateTime

# revision identifiers, used by Alembic.
revision: str = '9f09f1658d4f'
down_revision: Union[str, Sequence[str], None] = 'c71d2f8a9e35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


harness_session = sa.table(
    "harness_session",
    sa.column("id", sa.Integer),
    sa.column("pid", sa.Integer),
    sa.column("kind", sa.String),
    sa.column("created_at", UtcDateTime()),
    sa.column("last_active_at", UtcDateTime()),
    sa.column("process_started_at", UtcDateTime()),
    sa.column("ended_at", UtcDateTime()),
)


def _started_at(pid: int) -> datetime | None:
    try:
        return datetime.fromtimestamp(psutil.Process(pid).create_time(), timezone.utc)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('harness_session', schema=None) as batch_op:
        batch_op.add_column(sa.Column('process_started_at', UtcDateTime(), nullable=True))
        batch_op.add_column(sa.Column('ended_at', UtcDateTime(), nullable=True))

    # Classify every existing AGENT row against the process table now. A row stays open only
    # if a process holds its pid and started no later than the row's last sign of life
    # (registration or last prompt): a process that started afterwards reused the pid. Of
    # several open rows sharing one process (`/clear` starts a new session in the same
    # process), only the most recently active stays open. Every other row is ended as of now,
    # the first time kb observed it ended.
    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    rows = conn.execute(
        sa.select(
            harness_session.c.id,
            harness_session.c.pid,
            harness_session.c.created_at,
            harness_session.c.last_active_at,
        ).where(harness_session.c.kind == "AGENT")
    ).all()
    open_by_pid: dict[int, list[tuple[datetime, int, datetime]]] = {}
    ended_ids = []
    for row_id, pid, created_at, last_active_at in rows:
        last_seen = max(created_at, last_active_at) if last_active_at else created_at
        started = _started_at(pid)
        if started is not None and started <= last_seen:
            open_by_pid.setdefault(pid, []).append((last_seen, row_id, started))
        else:
            ended_ids.append(row_id)
    for candidates in open_by_pid.values():
        candidates.sort()
        *superseded, (_, current_id, started) = candidates
        ended_ids.extend(row_id for _, row_id, _ in superseded)
        conn.execute(
            harness_session.update().where(harness_session.c.id == current_id).values(process_started_at=started)
        )
    if ended_ids:
        conn.execute(harness_session.update().where(harness_session.c.id.in_(ended_ids)).values(ended_at=now))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('harness_session', schema=None) as batch_op:
        batch_op.drop_column('ended_at')
        batch_op.drop_column('process_started_at')
