"""add kind to harness_session

Revision ID: e2f01d01c430
Revises: 3e17c8e7e501
Create Date: 2026-08-27 16:27:34.703998

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f01d01c430'
down_revision: Union[str, Sequence[str], None] = '3e17c8e7e501'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # todo.severity's drop was autogenerate noticing another session's in-progress,
    # not-yet-migrated model change (models.py no longer declares Todo.severity, but the DB
    # still has the column from 3e17c8e7e501) -- deliberately not included here, that's a
    # separate migration for whoever owns that field to write.
    with op.batch_alter_table('harness_session', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'kind',
                sa.Enum('AGENT', 'HUMAN', name='harnesssessionkind', create_constraint=True),
                nullable=False,
                server_default='AGENT',
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('harness_session', schema=None) as batch_op:
        batch_op.drop_column('kind')
