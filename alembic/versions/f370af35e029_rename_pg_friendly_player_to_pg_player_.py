"""rename pg_friendly_player to pg_player, add friendly flag

Revision ID: f370af35e029
Revises: c2ad4a20d7c0
Create Date: 2026-07-04 00:39:12.573823

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f370af35e029'
down_revision: Union[str, Sequence[str], None] = 'c2ad4a20d7c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('pg_friendly_player', 'pg_player')
    with op.batch_alter_table('pg_player', schema=None) as batch_op:
        batch_op.add_column(sa.Column('friendly', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('pg_player', schema=None) as batch_op:
        batch_op.drop_column('friendly')
    op.rename_table('pg_player', 'pg_friendly_player')
