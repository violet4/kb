"""archived_link: split note into required title + reason

Revision ID: c279a025c90b
Revises: 26312c152473
Create Date: 2026-07-29 23:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c279a025c90b"
down_revision: Union[str, Sequence[str], None] = "26312c152473"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("archived_link") as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("reason", sa.Text(), nullable=True))

    # Backfill: existing rows' `note` actually described what the page is (a title), not
    # why it was saved -- move it to title, and record a reason pointing at the session
    # context those rows came from (kb Todo #75) since the real "why" wasn't captured
    # per-row at the time.
    op.execute(
        "UPDATE archived_link SET title = note, "
        "reason = 'Backfilled during 2026-07-29 title/reason split -- see kb Todo #75 for "
        "the original reason these were saved (Kavinsky death coverage).' "
        "WHERE title IS NULL"
    )

    with op.batch_alter_table("archived_link") as batch_op:
        batch_op.alter_column("title", nullable=False)
        batch_op.alter_column("reason", nullable=False)
        batch_op.drop_column("note")


def downgrade() -> None:
    with op.batch_alter_table("archived_link") as batch_op:
        batch_op.add_column(sa.Column("note", sa.Text(), nullable=True))

    op.execute("UPDATE archived_link SET note = title")

    with op.batch_alter_table("archived_link") as batch_op:
        batch_op.drop_column("reason")
        batch_op.drop_column("title")
