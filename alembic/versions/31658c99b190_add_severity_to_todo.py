"""add severity to todo

Revision ID: 31658c99b190
Revises: e2f01d01c430
Create Date: 2026-08-29 22:24:39.712575

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31658c99b190'
down_revision: Union[str, Sequence[str], None] = 'e2f01d01c430'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# An earlier, orphaned migration (3e17c8e7e501, committed 2026-08-27) had already added a
# `severity` column with values CRITICAL/MAJOR/MINOR, but was never wired into models.py or
# any CLI code -- a session ended mid-feature. This migration's own first attempt then added
# a second `severity` column via batch_alter_table's add_column, which on SQLite triggers a
# table recreate; that recreate carried forward every constraint already on the table verbatim
# (including several long-standing duplicate-named CHECK constraints on kind/effort/status --
# pre-existing drift, same class of bug as kb-engineering-16/20) plus the new one, leaving
# `todo` with two conflicting `severity` CHECK constraints ANDed together (effectively no value
# satisfied both). This migration recreates the table once, correctly: single CHECK per column,
# `ck_todo_<enum>` naming throughout, severity using LOW/MEDIUM/HIGH/CRITICAL.

_CREATE_NEW = """
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
    effort VARCHAR(8),
    defer_until DATETIME,
    tag_id INTEGER,
    embedding_model VARCHAR,
    embedding TEXT,
    urgent BOOLEAN NOT NULL,
    kind VARCHAR(7) DEFAULT 'TASK' NOT NULL,
    severity VARCHAR(8),
    PRIMARY KEY (id),
    CONSTRAINT ck_todo_todostatus CHECK (status IN ('PENDING', 'IN_PROGRESS', 'DONE', 'DROPPED')),
    CONSTRAINT ck_todo_wishlisteffort CHECK (effort IN ('GRAB', 'RESEARCH', 'PROJECT')),
    CONSTRAINT ck_todo_todokind CHECK (kind IN ('BUG', 'FEATURE', 'TASK', 'CHORE')),
    CONSTRAINT ck_todo_todoseverity CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    CONSTRAINT fk_todo_goal_id_goal FOREIGN KEY(goal_id) REFERENCES goal (id),
    CONSTRAINT fk_todo_context_id_context FOREIGN KEY(context_id) REFERENCES context (id),
    CONSTRAINT fk_todo_tag_id_tag FOREIGN KEY(tag_id) REFERENCES tag (id),
    CONSTRAINT fk_todo_blocked_by_id_todo FOREIGN KEY(blocked_by_id) REFERENCES todo (id)
)
"""

_COLUMNS = (
    "id, title, status, goal_id, context_id, notes, created_at, updated_at, blocked_by_id, "
    "effort, defer_until, tag_id, embedding_model, embedding, urgent, kind, severity"
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(_CREATE_NEW)
    op.execute(f"INSERT INTO todo_new ({_COLUMNS}) SELECT {_COLUMNS} FROM todo")
    op.execute("DROP TABLE todo")
    op.execute("ALTER TABLE todo_new RENAME TO todo")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('todo', schema=None) as batch_op:
        batch_op.drop_column('severity')
