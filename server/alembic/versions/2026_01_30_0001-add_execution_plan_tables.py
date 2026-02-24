"""Add execution plan and user privacy tables

Revision ID: 2026_01_30_0001
Revises: 2026_01_29_0001
Create Date: 2026-01-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2026_01_30_0001'
down_revision: Union[str, None] = '2026_01_29_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    """Check if a table already exists in the database."""
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    return name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    """Check if an index already exists on a table."""
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    try:
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)
    except Exception:
        return False


def upgrade() -> None:
    # Create userprivacy table (for /api/user/privacy endpoint)
    if not _table_exists('userprivacy'):
        op.create_table(
            'userprivacy',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('pricacy_setting', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id')
        )
    
    # Create execution_plan table
    if not _table_exists('execution_plan'):
        op.create_table(
            'execution_plan',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('project_id', sa.String(64), nullable=False),
            sa.Column('task_id', sa.String(64), nullable=False),
            sa.Column('plan_id', sa.String(128), nullable=False),
            sa.Column('title', sa.String(512), nullable=False),
            sa.Column('status', sa.SmallInteger(), nullable=False, default=1),
            sa.Column('steps', sa.JSON(), nullable=True),
            sa.Column('current_step_index', sa.Integer(), nullable=False, default=0),
            sa.Column('total_steps', sa.Integer(), nullable=False, default=0),
            sa.Column('completed_steps', sa.Integer(), nullable=False, default=0),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('id')
        )
    if not _index_exists('execution_plan', 'ix_execution_plan_user_id'):
        op.create_index('ix_execution_plan_user_id', 'execution_plan', ['user_id'])
    if not _index_exists('execution_plan', 'ix_execution_plan_project_id'):
        op.create_index('ix_execution_plan_project_id', 'execution_plan', ['project_id'])
    if not _index_exists('execution_plan', 'ix_execution_plan_task_id'):
        op.create_index('ix_execution_plan_task_id', 'execution_plan', ['task_id'])
    if not _index_exists('execution_plan', 'ix_execution_plan_plan_id'):
        op.create_index('ix_execution_plan_plan_id', 'execution_plan', ['plan_id'], unique=True)

    # Create plan_step table
    if not _table_exists('plan_step'):
        op.create_table(
            'plan_step',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('plan_id', sa.String(128), nullable=False),
            sa.Column('step_index', sa.Integer(), nullable=False, default=0),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('agent_type', sa.String(64), nullable=True),
            sa.Column('status', sa.SmallInteger(), nullable=False, default=0),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('result', sa.Text(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('duration_seconds', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('id')
        )
    if not _index_exists('plan_step', 'ix_plan_step_plan_id'):
        op.create_index('ix_plan_step_plan_id', 'plan_step', ['plan_id'])

    # Create plan_step_log table
    if not _table_exists('plan_step_log'):
        op.create_table(
            'plan_step_log',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('plan_id', sa.Integer(), nullable=False),
            sa.Column('step_index', sa.Integer(), nullable=False),
            sa.Column('log_index', sa.Integer(), nullable=False, default=0),
            sa.Column('toolkit', sa.String(128), nullable=False),
            sa.Column('method', sa.String(128), nullable=False),
            sa.Column('summary', sa.Text(), nullable=False),
            sa.Column('status', sa.String(32), nullable=False, default='completed'),
            sa.Column('full_output', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('id')
        )
    if not _index_exists('plan_step_log', 'ix_plan_step_log_plan_id'):
        op.create_index('ix_plan_step_log_plan_id', 'plan_step_log', ['plan_id'])
    if not _index_exists('plan_step_log', 'ix_plan_step_log_step_index'):
        op.create_index('ix_plan_step_log_step_index', 'plan_step_log', ['step_index'])


def downgrade() -> None:
    op.drop_index('ix_plan_step_log_step_index', table_name='plan_step_log')
    op.drop_index('ix_plan_step_log_plan_id', table_name='plan_step_log')
    op.drop_table('plan_step_log')
    
    op.drop_index('ix_plan_step_plan_id', table_name='plan_step')
    op.drop_table('plan_step')
    
    op.drop_index('ix_execution_plan_plan_id', table_name='execution_plan')
    op.drop_index('ix_execution_plan_task_id', table_name='execution_plan')
    op.drop_index('ix_execution_plan_project_id', table_name='execution_plan')
    op.drop_index('ix_execution_plan_user_id', table_name='execution_plan')
    op.drop_table('execution_plan')
    
    op.drop_table('userprivacy')
