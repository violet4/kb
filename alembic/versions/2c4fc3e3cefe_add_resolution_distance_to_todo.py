"""add resolution_distance to todo

Revision ID: 2c4fc3e3cefe
Revises: 31658c99b190
Create Date: 2026-08-29 23:39:41.155222

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2c4fc3e3cefe'
down_revision: Union[str, Sequence[str], None] = '31658c99b190'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# batch_alter_table's add_column, on SQLite, triggers a table recreate under the hood --
# and that recreate creates a CHECK constraint under both the correct `ck_todo_<enum>` name
# (matching Base's naming convention) AND a second, bare-named duplicate (`todoresolutiondistance`)
# with the same value list. Harmless functionally (both constraints agree), but it's the exact
# duplicate-CHECK-constraint drift kb-engineering-16/20 and 31658c99b190 (this table's own prior
# severity migration) already document and fixed once. This migration does the add as a raw-SQL
# table recreate instead, so the naming stays clean from the start rather than needing yet
# another cleanup migration later.

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
    resolution_distance VARCHAR(10),
    PRIMARY KEY (id),
    CONSTRAINT ck_todo_todostatus CHECK (status IN ('PENDING', 'IN_PROGRESS', 'DONE', 'DROPPED')),
    CONSTRAINT ck_todo_wishlisteffort CHECK (effort IN ('GRAB', 'RESEARCH', 'PROJECT')),
    CONSTRAINT ck_todo_todokind CHECK (kind IN ('BUG', 'FEATURE', 'TASK', 'CHORE')),
    CONSTRAINT ck_todo_todoseverity CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    CONSTRAINT ck_todo_todoresolutiondistance CHECK (resolution_distance IN ('MECHANICAL', 'DIAGNOSE', 'CLEAR_SHOT', 'OPEN')),
    CONSTRAINT fk_todo_goal_id_goal FOREIGN KEY(goal_id) REFERENCES goal (id),
    CONSTRAINT fk_todo_context_id_context FOREIGN KEY(context_id) REFERENCES context (id),
    CONSTRAINT fk_todo_tag_id_tag FOREIGN KEY(tag_id) REFERENCES tag (id),
    CONSTRAINT fk_todo_blocked_by_id_todo FOREIGN KEY(blocked_by_id) REFERENCES todo (id)
)
"""

_COLUMNS_BEFORE = (
    "id, title, status, goal_id, context_id, notes, created_at, updated_at, blocked_by_id, "
    "effort, defer_until, tag_id, embedding_model, embedding, urgent, kind, severity"
)


def upgrade() -> None:
    """Upgrade schema. `todo` has no `resolution_distance` column yet at this point in the
    migration chain, so the INSERT reads the pre-existing columns only and leaves the new
    column NULL on every row (its only valid state before anyone assesses it, see
    TodoResolutionDistance's docstring)."""
    op.execute(_CREATE_NEW)
    op.execute(f"INSERT INTO todo_new ({_COLUMNS_BEFORE}) SELECT {_COLUMNS_BEFORE} FROM todo")
    op.execute("DROP TABLE todo")
    op.execute("ALTER TABLE todo_new RENAME TO todo")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('todo', schema=None) as batch_op:
        batch_op.drop_column('resolution_distance')
