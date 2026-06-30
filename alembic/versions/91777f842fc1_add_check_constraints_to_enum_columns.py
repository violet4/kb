"""add CHECK constraints to enum columns

Revision ID: 91777f842fc1
Revises: b9c70474591c
Create Date: 2026-06-30 14:13:33.523340

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from models import (
    Collection, GoalStatus, PersonTier, TodoStatus, WishlistEffort,
    WishlistStatus,
)


# revision identifiers, used by Alembic.
revision: str = '91777f842fc1'
down_revision: Union[str, Sequence[str], None] = 'b9c70474591c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, enum class)
_ENUM_COLUMNS = [
    ("person", "tier", PersonTier),
    ("goal", "status", GoalStatus),
    ("todo", "status", TodoStatus),
    ("note", "collection", Collection),
    ("wishlist", "effort", WishlistEffort),
    ("wishlist", "status", WishlistStatus),
]


def upgrade() -> None:
    """Upgrade schema."""
    for table, column, enum_cls in _ENUM_COLUMNS:
        enum_type = sa.Enum(
            enum_cls, name=f"{table}_{column}",
            create_constraint=True, validate_strings=True,
        )
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column, existing_type=enum_type, type_=enum_type,
                existing_nullable=False,
            )


def downgrade() -> None:
    """Downgrade schema."""
    for table, column, enum_cls in _ENUM_COLUMNS:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column, existing_type=sa.Enum(enum_cls, name=f"{table}_{column}"),
                type_=sa.VARCHAR(), existing_nullable=False,
            )
