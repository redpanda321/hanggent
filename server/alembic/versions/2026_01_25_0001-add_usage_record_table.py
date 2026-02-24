"""Add usage_record table for tracking agent token usage and cost

Revision ID: add_usage_record_table
Revises: add_daytona_user_settings
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_usage_record_table'
down_revision: Union[str, None] = 'add_daytona_user_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create usage_record table
    op.create_table(
        'usage_record',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        sa.Column('task_id', sa.String(64), nullable=False, index=True),
        sa.Column('project_id', sa.String(64), nullable=True, index=True),
        
        # Agent information
        sa.Column('agent_name', sa.String(64), nullable=False, index=True),
        sa.Column('agent_step', sa.Integer(), nullable=True),
        
        # Model information
        sa.Column('model_platform', sa.String(64), nullable=False),
        sa.Column('model_type', sa.String(128), nullable=False),
        
        # Token counts
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        
        # Cost estimation
        sa.Column('estimated_cost', sa.Float(), nullable=False, server_default='0'),
        
        # Execution metadata
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('error_message', sa.String(512), nullable=True),
        
        # Additional context
        sa.Column('metadata', sa.JSON(), nullable=True),
        
        # Timestamps (from DefaultTimes)
        sa.Column('created_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
    )
    
    # Create composite indexes for common queries
    op.create_index('idx_usage_user_created', 'usage_record', ['user_id', 'created_at'])
    op.create_index('idx_usage_task_agent', 'usage_record', ['task_id', 'agent_name'])


def downgrade() -> None:
    op.drop_index('idx_usage_task_agent', table_name='usage_record')
    op.drop_index('idx_usage_user_created', table_name='usage_record')
    op.drop_table('usage_record')
