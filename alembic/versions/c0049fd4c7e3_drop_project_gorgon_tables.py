"""drop Project Gorgon tables and the gorgon note collection

Revision ID: c0049fd4c7e3
Revises: 9f09f1658d4f
Create Date: 2026-10-13 15:50:00

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0049fd4c7e3"
down_revision: Union[str, Sequence[str], None] = "9f09f1658d4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The PG data was exported as CSV before this migration (see ~/games/project_gorgon), and
# every upgrade backs the database up first; downgrade restores the empty tables only.
# note.collection's CHECK changes by raw-SQL table recreate, as in 752237ed2641.

_PG_TABLES_CHILD_FIRST = [
    "pg_mob_drop",
    "pg_hangout_item",
    "pg_npc_relation",
    "pg_quest",
    "pg_character",
    "pg_hangout",
    "pg_npc",
    "pg_npc_race",
    "pg_mob",
    "pg_skill",
    "pg_dungeon",
    "pg_player",
    "pg_item",
]


def _recreate_note(collections: str) -> list[str]:
    return [
        f"""
        CREATE TABLE note_new (
            id INTEGER NOT NULL,
            title VARCHAR NOT NULL,
            body TEXT NOT NULL,
            collection VARCHAR(11) NOT NULL,
            tags VARCHAR,
            embedding_model VARCHAR,
            embedding TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            deleted_at DATETIME,
            context_id INTEGER NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT ck_note_collection CHECK (collection IN ({collections})),
            CONSTRAINT fk_note_context_id_context FOREIGN KEY(context_id) REFERENCES context (id)
        )
        """,
        "INSERT INTO note_new SELECT * FROM note",
        "DROP TABLE note",
        "ALTER TABLE note_new RENAME TO note",
    ]


_PG_DDL_PARENT_FIRST = """
CREATE TABLE pg_item (
	id INTEGER NOT NULL, 
	kind VARCHAR, 
	sources TEXT, 
	max_stack_size INTEGER, 
	CONSTRAINT pk_pg_item PRIMARY KEY (id), 
	CONSTRAINT fk_pg_item_id_item FOREIGN KEY(id) REFERENCES item (id)
);
CREATE TABLE pg_dungeon (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	location VARCHAR, 
	level_min INTEGER, 
	level_max INTEGER, 
	notes TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, deleted_at DATETIME, 
	CONSTRAINT pk_pg_dungeon PRIMARY KEY (id), 
	CONSTRAINT uq_pg_dungeon_name UNIQUE (name)
);
CREATE TABLE pg_npc_race (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, deleted_at DATETIME, 
	CONSTRAINT pk_pg_npc_race PRIMARY KEY (id), 
	CONSTRAINT uq_pg_npc_race_name UNIQUE (name)
);
CREATE TABLE pg_npc (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	race_id INTEGER, 
	location VARCHAR, 
	notes TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, deleted_at DATETIME, 
	CONSTRAINT pk_pg_npc PRIMARY KEY (id), 
	CONSTRAINT fk_pg_npc_race_id_pg_npc_race FOREIGN KEY(race_id) REFERENCES pg_npc_race (id), 
	CONSTRAINT uq_pg_npc_name UNIQUE (name)
);
CREATE TABLE pg_quest (
	id INTEGER NOT NULL, 
	title VARCHAR NOT NULL, 
	giver_npc_id INTEGER NOT NULL, 
	completion_npc_id INTEGER, 
	status VARCHAR NOT NULL, 
	objectives TEXT, 
	rewards TEXT, 
	notes TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, deleted_at DATETIME, 
	CONSTRAINT pk_pg_quest PRIMARY KEY (id), 
	CONSTRAINT fk_pg_quest_completion_npc_id_pg_npc FOREIGN KEY(completion_npc_id) REFERENCES pg_npc (id), 
	CONSTRAINT fk_pg_quest_giver_npc_id_pg_npc FOREIGN KEY(giver_npc_id) REFERENCES pg_npc (id)
);
CREATE TABLE pg_mob (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	location VARCHAR, 
	notes TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, deleted_at DATETIME, 
	CONSTRAINT pk_pg_mob PRIMARY KEY (id), 
	CONSTRAINT uq_pg_mob_name UNIQUE (name)
);
CREATE TABLE pg_mob_drop (
	id INTEGER NOT NULL, 
	mob_id INTEGER NOT NULL, 
	item_id INTEGER NOT NULL, 
	notes TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, deleted_at DATETIME, 
	CONSTRAINT pk_pg_mob_drop PRIMARY KEY (id), 
	CONSTRAINT fk_pg_mob_drop_item_id_pg_item FOREIGN KEY(item_id) REFERENCES pg_item (id), 
	CONSTRAINT fk_pg_mob_drop_mob_id_pg_mob FOREIGN KEY(mob_id) REFERENCES pg_mob (id)
);
CREATE TABLE "pg_player" (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            notes TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            friendly BOOLEAN DEFAULT 1 NOT NULL, deleted_at DATETIME,
            CONSTRAINT pk_pg_player PRIMARY KEY (id),
            CONSTRAINT uq_pg_player_name UNIQUE (name)
        );
CREATE TABLE "pg_npc_relation" (
	id INTEGER NOT NULL, 
	character_id INTEGER NOT NULL, 
	npc_id INTEGER NOT NULL, 
	favor VARCHAR NOT NULL, 
	notes TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, deleted_at DATETIME, 
	CONSTRAINT pk_pg_npc_relation PRIMARY KEY (id), 
	CONSTRAINT fk_pg_npc_relation_npc_id_pg_npc FOREIGN KEY(npc_id) REFERENCES pg_npc (id), 
	CONSTRAINT fk_pg_npc_relation_character_id_pg_character FOREIGN KEY(character_id) REFERENCES pg_character (id)
);
CREATE TABLE pg_skill (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, deleted_at DATETIME, 
	CONSTRAINT pk_pg_skill PRIMARY KEY (id), 
	CONSTRAINT uq_pg_skill_name UNIQUE (name)
);
CREATE TABLE pg_hangout (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	npc_id INTEGER NOT NULL, 
	favor INTEGER NOT NULL, 
	skill_id INTEGER, 
	skill_xp INTEGER, 
	duration_minutes INTEGER NOT NULL, 
	is_repeatable BOOLEAN NOT NULL, 
	notes TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, deleted_at DATETIME, 
	CONSTRAINT pk_pg_hangout PRIMARY KEY (id), 
	CONSTRAINT fk_pg_hangout_npc_id_pg_npc FOREIGN KEY(npc_id) REFERENCES pg_npc (id), 
	CONSTRAINT fk_pg_hangout_skill_id_pg_skill FOREIGN KEY(skill_id) REFERENCES pg_skill (id), 
	CONSTRAINT uq_pg_hangout_name UNIQUE (name)
);
CREATE TABLE pg_hangout_item (
	id INTEGER NOT NULL, 
	hangout_id INTEGER NOT NULL, 
	item_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, deleted_at DATETIME, 
	CONSTRAINT pk_pg_hangout_item PRIMARY KEY (id), 
	CONSTRAINT fk_pg_hangout_item_hangout_id_pg_hangout FOREIGN KEY(hangout_id) REFERENCES pg_hangout (id), 
	CONSTRAINT fk_pg_hangout_item_item_id_pg_item FOREIGN KEY(item_id) REFERENCES pg_item (id)
);
CREATE TABLE "pg_character" (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	race TEXT NOT NULL, 
	is_druid BOOLEAN NOT NULL, 
	is_vampire BOOLEAN NOT NULL, 
	notes TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	hangout_id INTEGER, deleted_at DATETIME, 
	CONSTRAINT pk_pg_character PRIMARY KEY (id), 
	CONSTRAINT uq_pg_character_name UNIQUE (name), 
	CONSTRAINT fk_pg_character_hangout_id_pg_hangout FOREIGN KEY(hangout_id) REFERENCES pg_hangout (id)
);
"""


def upgrade() -> None:
    for table in _PG_TABLES_CHILD_FIRST:
        op.execute(f"DROP TABLE {table}")
    op.execute("DELETE FROM item WHERE game = 'pg'")
    for statement in _recreate_note("'ENGINEERING', 'PERSONAL', 'WORK', 'INBOX', 'ALL'"):
        op.execute(statement)


def downgrade() -> None:
    for statement in _recreate_note("'ENGINEERING', 'PERSONAL', 'GORGON', 'WORK', 'INBOX', 'ALL'"):
        op.execute(statement)
    for statement in _PG_DDL_PARENT_FIRST.split(";"):
        if statement.strip():
            op.execute(statement)
