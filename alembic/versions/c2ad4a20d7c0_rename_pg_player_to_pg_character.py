"""rename pg_player to pg_character

Revision ID: c2ad4a20d7c0
Revises: 3e3b68c41098
Create Date: 2026-07-04 00:17:41.757021

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c2ad4a20d7c0'
down_revision: Union[str, Sequence[str], None] = '3e3b68c41098'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('pg_player', 'pg_character')
    with op.batch_alter_table('pg_npc_relation', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_pg_npc_relation_player_id_pg_player'), type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('fk_pg_npc_relation_player_id_pg_character'), 'pg_character', ['player_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('pg_npc_relation', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_pg_npc_relation_player_id_pg_character'), type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('fk_pg_npc_relation_player_id_pg_player'), 'pg_player', ['player_id'], ['id'])
    op.rename_table('pg_character', 'pg_player')
