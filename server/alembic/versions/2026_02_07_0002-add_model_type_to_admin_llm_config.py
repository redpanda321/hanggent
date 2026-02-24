"""Add model_type to admin_llm_config

Revision ID: 2026_02_07_0002
Revises: 2026_02_07_0001
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# revision identifiers, used by Alembic.
revision: str = '2026_02_07_0002'
down_revision: Union[str, None] = '2026_02_07_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists('admin_llm_config', 'model_type'):
        op.add_column(
            'admin_llm_config',
            sa.Column('model_type', sa.String(128), nullable=True, server_default=''),
        )


def downgrade() -> None:
    op.drop_column('admin_llm_config', 'model_type')
