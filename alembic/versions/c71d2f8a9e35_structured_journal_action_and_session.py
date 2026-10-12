"""journal: action and session columns; log_entry.source_ref folds into journal

Revision ID: c71d2f8a9e35
Revises: a3c91e7d4b20
Create Date: 2026-10-12 14:30:00

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c71d2f8a9e35'
down_revision: Union[str, Sequence[str], None] = 'a3c91e7d4b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw-SQL table recreate (see 752237ed2641 for why not batch mode). Existing journal rows get
# an action from their shape: a row naming a field is a change (UPDATE), anything else is a
# hand-written NOTE. Each log_entry.source_ref that names a registered session becomes that
# entry's CREATE row, dated when the entry was created; a source_ref naming a session that
# never registered has no harness_session row to point at and is dropped with the column.

_UP = [
    """
    CREATE TABLE journal_new (
        id INTEGER NOT NULL,
        entity_type VARCHAR NOT NULL,
        entity_id INTEGER NOT NULL,
        action VARCHAR(6) NOT NULL,
        field VARCHAR,
        old_value TEXT,
        new_value TEXT,
        note TEXT,
        session_id INTEGER,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        deleted_at DATETIME,
        CONSTRAINT pk_journal PRIMARY KEY (id),
        CONSTRAINT ck_journal_journalaction CHECK (action IN ('CREATE', 'READ', 'UPDATE', 'DELETE', 'NOTE')),
        CONSTRAINT fk_journal_session_id_harness_session FOREIGN KEY(session_id) REFERENCES harness_session (id)
    )
    """,
    """
    INSERT INTO journal_new (id, entity_type, entity_id, action, field, old_value, new_value, note,
        session_id, created_at, updated_at, deleted_at)
    SELECT id, entity_type, entity_id, CASE WHEN field IS NOT NULL THEN 'UPDATE' ELSE 'NOTE' END,
        field, old_value, new_value, note, NULL, created_at, updated_at, deleted_at
    FROM journal
    """,
    """
    INSERT INTO journal_new (entity_type, entity_id, action, session_id, created_at, updated_at)
    SELECT 'LogEntry', l.id, 'CREATE', h.id, l.created_at, l.created_at
    FROM log_entry l JOIN harness_session h ON h.harness_id = l.source_ref
    ORDER BY l.created_at
    """,
    "DROP TABLE journal",
    "ALTER TABLE journal_new RENAME TO journal",
    "CREATE INDEX ix_journal_entity ON journal (entity_type, entity_id)",
    "CREATE INDEX ix_journal_session_id ON journal (session_id)",
    "ALTER TABLE log_entry DROP COLUMN source_ref",
]

_DOWN = [
    "ALTER TABLE log_entry ADD COLUMN source_ref VARCHAR",
    """
    UPDATE log_entry SET source_ref = (
        SELECT h.harness_id FROM journal j JOIN harness_session h ON h.id = j.session_id
        WHERE j.entity_type = 'LogEntry' AND j.entity_id = log_entry.id AND j.action = 'CREATE'
    )
    """,
    """
    CREATE TABLE journal_old (
        id INTEGER NOT NULL,
        entity_type VARCHAR NOT NULL,
        entity_id INTEGER NOT NULL,
        field VARCHAR,
        old_value TEXT,
        new_value TEXT,
        note TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        deleted_at DATETIME,
        CONSTRAINT pk_journal PRIMARY KEY (id)
    )
    """,
    """
    INSERT INTO journal_old
    SELECT id, entity_type, entity_id, field, old_value, new_value, note, created_at, updated_at, deleted_at
    FROM journal WHERE action IN ('UPDATE', 'NOTE')
    """,
    "DROP TABLE journal",
    "ALTER TABLE journal_old RENAME TO journal",
]


def upgrade() -> None:
    for statement in _UP:
        op.execute(statement)


def downgrade() -> None:
    for statement in _DOWN:
        op.execute(statement)
