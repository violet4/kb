"""require context or tag on every record

Revision ID: feb89426c3f1
Revises: 0246b4af596c
Create Date: 2026-10-11 15:06:02.179732

"""
import re
from typing import Callable, Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'feb89426c3f1'
down_revision: Union[str, Sequence[str], None] = '0246b4af596c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Rows that carry a tag instead of a context (HasContextOrTag): exactly one of the two.
_CONTEXT_OR_TAG_TABLES = ["todo", "goal", "daily", "event", "idea", "timer"]
# Rows with no tag support: context_id NOT NULL.
_CONTEXT_ONLY_TABLES = ["note", "log_entry"]

_CHECK = "(context_id IS NULL) != (tag_id IS NULL)"

# Each table is rebuilt in raw SQL (CREATE new, copy, DROP, RENAME) from its own live DDL in
# sqlite_master, edited textually -- alembic's batch mode is unreliable on these tables' enum
# CHECK constraints (see the on-hold GoalStatus migration, 752237ed2641), and reading the live
# DDL keeps every other user's column order and existing constraints exactly as they are.


def _sub_once(pattern: str, repl: str, sql: str, table: str) -> str:
    new_sql, n = re.subn(pattern, repl, sql)
    if n != 1:
        raise RuntimeError(f"{table}: expected exactly one match for {pattern!r} in its DDL, found {n}")
    return new_sql


def _rebuild(table: str, edit: Callable[[str], str]) -> None:
    conn = op.get_bind()
    sql = conn.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :t"), {"t": table}
    ).scalar_one()
    extras = conn.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE tbl_name = :t AND type IN ('index', 'trigger') AND sql IS NOT NULL"),
        {"t": table},
    ).scalars().all()
    new_sql = _sub_once(r'^CREATE TABLE "?' + table + r'"?', f'CREATE TABLE "{table}_new"', edit(sql), table)
    op.execute(new_sql)
    op.execute(f'INSERT INTO "{table}_new" SELECT * FROM "{table}"')
    op.execute(f'DROP TABLE "{table}"')
    op.execute(f'ALTER TABLE "{table}_new" RENAME TO "{table}"')
    for extra in extras:
        op.execute(extra)


def _add_check(table: str) -> Callable[[str], str]:
    return lambda sql: _sub_once(
        r"\n\)\s*$", f",\n\tCONSTRAINT ck_{table}_context_xor_tag CHECK ({_CHECK})\n)", sql, table
    )


def _drop_check(table: str) -> Callable[[str], str]:
    return lambda sql: _sub_once(r",\s*CONSTRAINT ck_" + table + r"_context_xor_tag CHECK \([^\n]*\)", "", sql, table)


def _context_not_null(table: str) -> Callable[[str], str]:
    return lambda sql: _sub_once(r"\bcontext_id INTEGER(?= *,)", "context_id INTEGER NOT NULL", sql, table)


def _context_nullable(table: str) -> Callable[[str], str]:
    return lambda sql: _sub_once(r"\bcontext_id INTEGER NOT NULL\b", "context_id INTEGER", sql, table)


def upgrade() -> None:
    """Upgrade schema."""
    # Unplaced rows go to the fixed `inbox` Context, the same place unfiled rows already live.
    op.execute(
        "INSERT INTO context (name, created_at, updated_at) "
        "SELECT 'inbox', datetime('now'), datetime('now') "
        "WHERE NOT EXISTS (SELECT 1 FROM context WHERE name = 'inbox')"
    )
    inbox = "(SELECT id FROM context WHERE name = 'inbox')"
    for table in _CONTEXT_OR_TAG_TABLES:
        op.execute(f"UPDATE {table} SET context_id = {inbox} WHERE context_id IS NULL AND tag_id IS NULL")
        _rebuild(table, _add_check(table))
    for table in _CONTEXT_ONLY_TABLES:
        op.execute(f"UPDATE {table} SET context_id = {inbox} WHERE context_id IS NULL")
        _rebuild(table, _context_not_null(table))


def downgrade() -> None:
    """Downgrade schema. The inbox backfill is kept: it cannot be told apart from rows filed there on purpose."""
    for table in _CONTEXT_OR_TAG_TABLES:
        _rebuild(table, _drop_check(table))
    for table in _CONTEXT_ONLY_TABLES:
        _rebuild(table, _context_nullable(table))
