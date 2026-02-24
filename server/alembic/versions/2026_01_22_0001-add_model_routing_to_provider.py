"""Add model routing fields to provider table

Revision ID: add_model_routing_to_provider
Revises: add_timestamp_to_chat_step
Create Date: 2026-01-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite


# revision identifiers, used by Alembic.
revision: str = 'add_model_routing_to_provider'
down_revision: Union[str, None] = 'add_timestamp_to_chat_step'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add assigned_agents column (JSON array of agent names)
    op.add_column('provider', sa.Column('assigned_agents', sa.JSON(), nullable=True, server_default='[]'))
    
    # Add cost_tier column (cheap, standard, premium)
    op.add_column('provider', sa.Column('cost_tier', sa.String(20), nullable=True, server_default='standard'))


def downgrade() -> None:
    op.drop_column('provider', 'assigned_agents')
    op.drop_column('provider', 'cost_tier')
