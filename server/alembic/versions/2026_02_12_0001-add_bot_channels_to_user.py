"""Add bot_channels column to user table

Revision ID: 2026_02_12_0001
Revises: 2026_02_08_0001
Create Date: 2026-02-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# revision identifiers, used by Alembic.
revision: str = '2026_02_12_0001'
down_revision: Union[str, None] = '2026_02_08_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists('user', 'bot_channels'):
        op.add_column('user', sa.Column('bot_channels', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'bot_channels')
