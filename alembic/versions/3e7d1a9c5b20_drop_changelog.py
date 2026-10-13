"""drop changelog

Revision ID: 3e7d1a9c5b20
Revises: c0049fd4c7e3
Create Date: 2026-10-13 16:20:00

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3e7d1a9c5b20'
down_revision: Union[str, Sequence[str], None] = 'c0049fd4c7e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE changelog")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE changelog (
            id INTEGER NOT NULL,
            entity_table VARCHAR NOT NULL,
            entity_id INTEGER NOT NULL,
            field VARCHAR NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            deleted_at DATETIME,
            PRIMARY KEY (id)
        )
        """
    )
