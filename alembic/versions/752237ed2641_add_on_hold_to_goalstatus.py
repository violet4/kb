"""fix enum CHECK constraint names + add ON_HOLD to GoalStatus

Revision ID: 752237ed2641
Revises: f74233a58023
Create Date: 2026-07-02 19:53:39.671409

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '752237ed2641'
down_revision: Union[str, Sequence[str], None] = 'f74233a58023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The original CHECK-constraint migration (91777f842fc1) named constraints "{table}_{column}"
# (e.g. "goal_status"), which does not match Base's naming convention or what SQLAlchemy's
# Enum(..., create_constraint=True) derives internally. alembic's batch_alter_table +
# drop_constraint could not reliably operate on these mismatched names — it looked for a name
# derived from target_metadata (a THIRD name, different from both the on-disk name and what
# Base.metadata.tables[...] reports) and raised "No such constraint". See kb-engineering-<id>
# for the full debugging trail; this migration sidesteps alembic's batch/constraint machinery
# entirely and does the table recreate as raw SQL, which is fully predictable on SQLite.
#
# This migration does two things in one pass, since both require the same recreate:
# 1. Renames all 6 mismatched CHECK constraints so future migrations don't hit this again.
# 2. Adds ON_HOLD to goal.status's allowed values.

_STATEMENTS_UP = [
    # person.tier
    """
    CREATE TABLE person_new (
        id INTEGER NOT NULL,
        name VARCHAR NOT NULL,
        tier VARCHAR(13) NOT NULL,
        closeness INTEGER NOT NULL,
        last_contacted DATETIME,
        reach_out_every_days INTEGER,
        notes TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT ck_person_persontier CHECK (tier IN ('CLOSE', 'ACQUAINTANCE', 'PUBLIC_FIGURE'))
    )
    """,
    "INSERT INTO person_new SELECT * FROM person",
    "DROP TABLE person",
    "ALTER TABLE person_new RENAME TO person",

    # goal.status (also adds ON_HOLD)
    """
    CREATE TABLE goal_new (
        id INTEGER NOT NULL,
        title VARCHAR NOT NULL,
        description TEXT,
        status VARCHAR(9) NOT NULL,
        context_id INTEGER,
        notes TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT ck_goal_goalstatus CHECK (status IN ('ACTIVE', 'ON_HOLD', 'COMPLETED', 'ABANDONED')),
        FOREIGN KEY(context_id) REFERENCES context (id)
    )
    """,
    "INSERT INTO goal_new SELECT * FROM goal",
    "DROP TABLE goal",
    "ALTER TABLE goal_new RENAME TO goal",

    # todo.status
    """
    CREATE TABLE todo_new (
        id INTEGER NOT NULL,
        title VARCHAR NOT NULL,
        status VARCHAR(11) NOT NULL,
        goal_id INTEGER,
        context_id INTEGER,
        notes TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        blocked_by_id INTEGER,
        PRIMARY KEY (id),
        CONSTRAINT ck_todo_todostatus CHECK (status IN ('PENDING', 'IN_PROGRESS', 'DONE', 'DROPPED')),
        CONSTRAINT fk_todo_blocked_by_id_todo FOREIGN KEY(blocked_by_id) REFERENCES todo (id),
        FOREIGN KEY(context_id) REFERENCES context (id),
        FOREIGN KEY(goal_id) REFERENCES goal (id)
    )
    """,
    "INSERT INTO todo_new SELECT * FROM todo",
    "DROP TABLE todo",
    "ALTER TABLE todo_new RENAME TO todo",

    # note.collection
    """
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
        PRIMARY KEY (id),
        CONSTRAINT ck_note_collection CHECK (collection IN ('ENGINEERING', 'PERSONAL', 'GORGON', 'WORK', 'ALL'))
    )
    """,
    "INSERT INTO note_new SELECT * FROM note",
    "DROP TABLE note",
    "ALTER TABLE note_new RENAME TO note",

    # wishlist.effort, wishlist.status
    """
    CREATE TABLE wishlist_new (
        id INTEGER NOT NULL,
        title VARCHAR NOT NULL,
        description TEXT,
        price_min NUMERIC(10, 2),
        price_max NUMERIC(10, 2),
        importance INTEGER NOT NULL,
        urgency INTEGER NOT NULL,
        effort VARCHAR(8) NOT NULL,
        clarity INTEGER NOT NULL,
        status VARCHAR(8) NOT NULL,
        context_id INTEGER,
        notes TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        priority INTEGER,
        PRIMARY KEY (id),
        CONSTRAINT ck_wishlist_wishlisteffort CHECK (effort IN ('GRAB', 'RESEARCH', 'PROJECT')),
        CONSTRAINT ck_wishlist_wishliststatus CHECK (status IN ('ACTIVE', 'ACQUIRED', 'DROPPED')),
        FOREIGN KEY(context_id) REFERENCES context (id)
    )
    """,
    "INSERT INTO wishlist_new SELECT * FROM wishlist",
    "DROP TABLE wishlist",
    "ALTER TABLE wishlist_new RENAME TO wishlist",
]

_STATEMENTS_DOWN = [
    """
    CREATE TABLE goal_new (
        id INTEGER NOT NULL,
        title VARCHAR NOT NULL,
        description TEXT,
        status VARCHAR(9) NOT NULL,
        context_id INTEGER,
        notes TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT goal_status CHECK (status IN ('ACTIVE', 'COMPLETED', 'ABANDONED')),
        FOREIGN KEY(context_id) REFERENCES context (id)
    )
    """,
    "INSERT INTO goal_new SELECT * FROM goal",
    "DROP TABLE goal",
    "ALTER TABLE goal_new RENAME TO goal",

    """
    CREATE TABLE person_new (
        id INTEGER NOT NULL,
        name VARCHAR NOT NULL,
        tier VARCHAR(13) NOT NULL,
        closeness INTEGER NOT NULL,
        last_contacted DATETIME,
        reach_out_every_days INTEGER,
        notes TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT person_tier CHECK (tier IN ('CLOSE', 'ACQUAINTANCE', 'PUBLIC_FIGURE'))
    )
    """,
    "INSERT INTO person_new SELECT * FROM person",
    "DROP TABLE person",
    "ALTER TABLE person_new RENAME TO person",

    """
    CREATE TABLE todo_new (
        id INTEGER NOT NULL,
        title VARCHAR NOT NULL,
        status VARCHAR(11) NOT NULL,
        goal_id INTEGER,
        context_id INTEGER,
        notes TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        blocked_by_id INTEGER,
        PRIMARY KEY (id),
        CONSTRAINT todo_status CHECK (status IN ('PENDING', 'IN_PROGRESS', 'DONE', 'DROPPED')),
        CONSTRAINT fk_todo_blocked_by_id_todo FOREIGN KEY(blocked_by_id) REFERENCES todo (id),
        FOREIGN KEY(context_id) REFERENCES context (id),
        FOREIGN KEY(goal_id) REFERENCES goal (id)
    )
    """,
    "INSERT INTO todo_new SELECT * FROM todo",
    "DROP TABLE todo",
    "ALTER TABLE todo_new RENAME TO todo",

    """
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
        PRIMARY KEY (id),
        CONSTRAINT note_collection CHECK (collection IN ('ENGINEERING', 'PERSONAL', 'GORGON', 'WORK', 'ALL'))
    )
    """,
    "INSERT INTO note_new SELECT * FROM note",
    "DROP TABLE note",
    "ALTER TABLE note_new RENAME TO note",

    """
    CREATE TABLE wishlist_new (
        id INTEGER NOT NULL,
        title VARCHAR NOT NULL,
        description TEXT,
        price_min NUMERIC(10, 2),
        price_max NUMERIC(10, 2),
        importance INTEGER NOT NULL,
        urgency INTEGER NOT NULL,
        effort VARCHAR(8) NOT NULL,
        clarity INTEGER NOT NULL,
        status VARCHAR(8) NOT NULL,
        context_id INTEGER,
        notes TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        priority INTEGER,
        PRIMARY KEY (id),
        CONSTRAINT wishlist_effort CHECK (effort IN ('GRAB', 'RESEARCH', 'PROJECT')),
        CONSTRAINT wishlist_status CHECK (status IN ('ACTIVE', 'ACQUIRED', 'DROPPED')),
        FOREIGN KEY(context_id) REFERENCES context (id)
    )
    """,
    "INSERT INTO wishlist_new SELECT * FROM wishlist",
    "DROP TABLE wishlist",
    "ALTER TABLE wishlist_new RENAME TO wishlist",
]


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    for stmt in _STATEMENTS_UP:
        conn.exec_driver_sql(stmt)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    for stmt in _STATEMENTS_DOWN:
        conn.exec_driver_sql(stmt)
