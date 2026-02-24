"""Add deleted_at column to execution plan tables

Revision ID: 2026_02_08_0001
Revises: 2026_02_07_0002
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# revision identifiers, used by Alembic.
revision: str = '2026_02_08_0001'
down_revision: Union[str, None] = '2026_02_07_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists('execution_plan', 'deleted_at'):
        op.add_column('execution_plan', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    if not _column_exists('plan_step', 'deleted_at'):
        op.add_column('plan_step', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    if not _column_exists('plan_step_log', 'deleted_at'):
        op.add_column('plan_step_log', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('plan_step_log', 'deleted_at')
    op.drop_column('plan_step', 'deleted_at')
    op.drop_column('execution_plan', 'deleted_at')
