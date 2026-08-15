"""add system_level to instruction

Revision ID: da1fb439f9e5
Revises: c311ae1e2dae
Create Date: 2026-08-15 02:22:35.337289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da1fb439f9e5'
down_revision: Union[str, Sequence[str], None] = 'c311ae1e2dae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add system_level only -- parent_id is dropped in a later migration, after its data is
    backfilled into EntityLink rows (see kb Todo #127). server_default required since the
    table already has rows and the column is NOT NULL."""
    with op.batch_alter_table('instruction', schema=None) as batch_op:
        batch_op.add_column(sa.Column('system_level', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('instruction', schema=None) as batch_op:
        batch_op.alter_column('system_level', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('instruction', schema=None) as batch_op:
        batch_op.drop_column('system_level')
