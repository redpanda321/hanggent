"""Add admin LLM config and model pricing tables

Revision ID: 2026_02_07_0001
Revises: 2026_01_30_0001
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# revision identifiers, used by Alembic.
revision: str = '2026_02_07_0001'
down_revision: Union[str, None] = '2026_01_30_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    # Create admin_llm_config table
    if _table_exists('admin_llm_config'):
        return  # Both tables likely already exist
    op.create_table(
        'admin_llm_config',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('provider_name', sa.String(64), nullable=False, index=True),
        sa.Column('display_name', sa.String(128), nullable=True, server_default=''),
        sa.Column('api_key', sa.Text(), nullable=False),
        sa.Column('endpoint_url', sa.String(512), nullable=True, server_default=''),
        sa.Column('extra_config', sa.JSON(), nullable=True),
        sa.Column('status', sa.SmallInteger(), nullable=True, server_default='1'),
        sa.Column('priority', sa.SmallInteger(), nullable=True, server_default='0'),
        sa.Column('rate_limit_rpm', sa.Integer(), nullable=True),
        sa.Column('rate_limit_tpm', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True, server_default=''),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_name', name='uix_admin_llm_config_provider'),
    )

    # Create admin_model_pricing table
    if _table_exists('admin_model_pricing'):
        return
    op.create_table(
        'admin_model_pricing',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('provider_name', sa.String(64), nullable=False, index=True),
        sa.Column('model_name', sa.String(128), nullable=False, index=True),
        sa.Column('display_name', sa.String(256), nullable=True, server_default=''),
        sa.Column('input_price_per_million', sa.Numeric(10, 4), nullable=True, server_default='0'),
        sa.Column('output_price_per_million', sa.Numeric(10, 4), nullable=True, server_default='0'),
        sa.Column('cost_tier', sa.String(20), nullable=True, server_default="'standard'"),
        sa.Column('context_length', sa.Integer(), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True, server_default=''),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_name', 'model_name', name='uix_admin_model_pricing_provider_model'),
    )


def downgrade() -> None:
    op.drop_table('admin_model_pricing')
    op.drop_table('admin_llm_config')
