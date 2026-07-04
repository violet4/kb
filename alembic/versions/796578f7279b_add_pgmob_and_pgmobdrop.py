"""add PgMob and PgMobDrop

Revision ID: 796578f7279b
Revises: f370af35e029
Create Date: 2026-07-04 14:51:34.857500

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '796578f7279b'
down_revision: Union[str, Sequence[str], None] = 'f370af35e029'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('pg_mob',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('location', sa.String(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pg_mob')),
    sa.UniqueConstraint('name', name=op.f('uq_pg_mob_name'))
    )
    op.create_table('pg_mob_drop',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('mob_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['pg_item.id'], name=op.f('fk_pg_mob_drop_item_id_pg_item')),
    sa.ForeignKeyConstraint(['mob_id'], ['pg_mob.id'], name=op.f('fk_pg_mob_drop_mob_id_pg_mob')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pg_mob_drop'))
    )

    # pg_character and pg_player each kept their PK/UNIQUE constraint names from before their
    # respective table renames (op.rename_table only renames the table itself, not constraints
    # inside it, on SQLite). Fix both via table recreate, same technique as kb-engineering-16.
    op.execute("""
        CREATE TABLE pg_character_new (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            race TEXT NOT NULL,
            is_druid BOOLEAN NOT NULL,
            is_vampire BOOLEAN NOT NULL,
            notes TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            CONSTRAINT pk_pg_character PRIMARY KEY (id),
            CONSTRAINT uq_pg_character_name UNIQUE (name)
        )
    """)
    op.execute("INSERT INTO pg_character_new SELECT * FROM pg_character")
    op.execute("DROP TABLE pg_character")
    op.execute("ALTER TABLE pg_character_new RENAME TO pg_character")

    op.execute("""
        CREATE TABLE pg_player_new (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            notes TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            friendly BOOLEAN DEFAULT 1 NOT NULL,
            CONSTRAINT pk_pg_player PRIMARY KEY (id),
            CONSTRAINT uq_pg_player_name UNIQUE (name)
        )
    """)
    op.execute("INSERT INTO pg_player_new SELECT * FROM pg_player")
    op.execute("DROP TABLE pg_player")
    op.execute("ALTER TABLE pg_player_new RENAME TO pg_player")

    # pg_npc_relation.player_id -> pg_character.id was created pointing at the old pg_player
    # table before the rename; SQLite FKs aren't enforced by column name matching post-rename,
    # but recreate pg_character above invalidates the old rowid-based reference target, so
    # this FK must be verified/recreated with the batch helper for a clean constraint name too.
    with op.batch_alter_table('pg_npc_relation', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_pg_npc_relation_player_id_pg_character'), type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('fk_pg_npc_relation_player_id_pg_character'), 'pg_character', ['player_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('pg_npc_relation', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_pg_npc_relation_player_id_pg_character'), type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('fk_pg_npc_relation_player_id_pg_character'), 'pg_character', ['player_id'], ['id'])

    op.execute("""
        CREATE TABLE pg_character_old (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            race TEXT NOT NULL,
            is_druid BOOLEAN NOT NULL,
            is_vampire BOOLEAN NOT NULL,
            notes TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            CONSTRAINT pk_pg_player PRIMARY KEY (id),
            CONSTRAINT uq_pg_player_name UNIQUE (name)
        )
    """)
    op.execute("INSERT INTO pg_character_old SELECT * FROM pg_character")
    op.execute("DROP TABLE pg_character")
    op.execute("ALTER TABLE pg_character_old RENAME TO pg_character")

    op.execute("""
        CREATE TABLE pg_player_old (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            notes TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            friendly BOOLEAN DEFAULT 1 NOT NULL,
            CONSTRAINT pk_pg_friendly_player PRIMARY KEY (id),
            CONSTRAINT uq_pg_friendly_player_name UNIQUE (name)
        )
    """)
    op.execute("INSERT INTO pg_player_old SELECT * FROM pg_player")
    op.execute("DROP TABLE pg_player")
    op.execute("ALTER TABLE pg_player_old RENAME TO pg_player")

    op.drop_table('pg_mob_drop')
    op.drop_table('pg_mob')
