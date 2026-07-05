"""rename pg_npc_relation.player_id to character_id

Revision ID: 58147824a035
Revises: 796578f7279b
Create Date: 2026-07-05 09:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '58147824a035'
down_revision: Union[str, Sequence[str], None] = '796578f7279b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('pg_npc_relation', schema=None) as batch_op:
        batch_op.drop_constraint('fk_pg_npc_relation_player_id_pg_character', type_='foreignkey')
        batch_op.alter_column('player_id', new_column_name='character_id')
        batch_op.create_foreign_key(
            batch_op.f('fk_pg_npc_relation_character_id_pg_character'),
            'pg_character', ['character_id'], ['id'],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('pg_npc_relation', schema=None) as batch_op:
        batch_op.drop_constraint('fk_pg_npc_relation_character_id_pg_character', type_='foreignkey')
        batch_op.alter_column('character_id', new_column_name='player_id')
        batch_op.create_foreign_key(
            batch_op.f('fk_pg_npc_relation_player_id_pg_character'),
            'pg_character', ['player_id'], ['id'],
        )
