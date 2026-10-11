"""require context on wishlist

Revision ID: 5eb3fe6a2cb0
Revises: feb89426c3f1
Create Date: 2026-10-11 15:53:00

"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5eb3fe6a2cb0'
down_revision: Union[str, Sequence[str], None] = 'feb89426c3f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same raw-SQL rebuild from the live DDL as feb89426c3f1 (see its comment for why not batch mode).


def _rebuild(pattern: str, repl: str) -> None:
    conn = op.get_bind()
    sql = conn.execute(sa.text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'wishlist'")).scalar_one()
    extras = conn.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE tbl_name = 'wishlist' AND type IN ('index', 'trigger') AND sql IS NOT NULL")
    ).scalars().all()
    for pat, rep in ((pattern, repl), (r'^CREATE TABLE "?wishlist"?', 'CREATE TABLE "wishlist_new"')):
        sql, n = re.subn(pat, rep, sql)
        if n != 1:
            raise RuntimeError(f"wishlist: expected exactly one match for {pat!r} in its DDL, found {n}")
    op.execute(sql)
    op.execute('INSERT INTO "wishlist_new" SELECT * FROM "wishlist"')
    op.execute('DROP TABLE "wishlist"')
    op.execute('ALTER TABLE "wishlist_new" RENAME TO "wishlist"')
    for extra in extras:
        op.execute(extra)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "INSERT INTO context (name, created_at, updated_at) "
        "SELECT 'inbox', datetime('now'), datetime('now') "
        "WHERE NOT EXISTS (SELECT 1 FROM context WHERE name = 'inbox')"
    )
    op.execute(
        "UPDATE wishlist SET context_id = (SELECT id FROM context WHERE name = 'inbox') WHERE context_id IS NULL"
    )
    _rebuild(r"\bcontext_id INTEGER(?= *,)", "context_id INTEGER NOT NULL")


def downgrade() -> None:
    """Downgrade schema. The inbox backfill is kept: it cannot be told apart from rows filed there on purpose."""
    _rebuild(r"\bcontext_id INTEGER NOT NULL\b", "context_id INTEGER")
