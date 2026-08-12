"""add INBOX to Collection

Revision ID: a1c2e4f7b9d3
Revises: d40fc45e46ef
Create Date: 2026-08-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c2e4f7b9d3'
down_revision: Union[str, Sequence[str], None] = 'd40fc45e46ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw-SQL table recreate (see kb-engineering-16) since SQLite CHECK constraints on Enum
# columns can't be altered via batch_alter_table/alter_column.

_UP = [
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
        CONSTRAINT ck_note_collection CHECK (collection IN ('ENGINEERING', 'PERSONAL', 'GORGON', 'WORK', 'INBOX', 'ALL'))
    )
    """,
    "INSERT INTO note_new SELECT * FROM note",
    "DROP TABLE note",
    "ALTER TABLE note_new RENAME TO note",
]

_DOWN = [
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
    "INSERT INTO note_new SELECT * FROM note WHERE collection != 'INBOX'",
    "DROP TABLE note",
    "ALTER TABLE note_new RENAME TO note",
]


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    for stmt in _UP:
        conn.exec_driver_sql(stmt)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    for stmt in _DOWN:
        conn.exec_driver_sql(stmt)
