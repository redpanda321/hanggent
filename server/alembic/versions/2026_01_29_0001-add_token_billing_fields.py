"""Add token-based billing fields

Adds spending_limit and monthly_spending_alert_sent to User table.
Creates user_usage_summary table for monthly billing tracking.

Revision ID: 0001
Revises: add_job_hunt_tables
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


# revision identifiers, used by Alembic.
revision = '2026_01_29_0001'
down_revision = 'add_job_hunt_tables'
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    return name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    try:
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)
    except Exception:
        return False


def upgrade() -> None:
    # Add token-based billing fields to user table
    if not _column_exists('user', 'spending_limit'):
        op.add_column('user', sa.Column('spending_limit', sa.Float(), server_default='100.0', nullable=True))
    if not _column_exists('user', 'monthly_spending_alert_sent'):
        op.add_column('user', sa.Column('monthly_spending_alert_sent', sa.Boolean(), server_default='0', nullable=True))
    
    # Create user_usage_summary table for monthly billing tracking
    if not _table_exists('user_usage_summary'):
        op.create_table(
            'user_usage_summary',
            sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('billing_year', sa.Integer(), nullable=False),
            sa.Column('billing_month', sa.Integer(), nullable=False),
            sa.Column('total_input_tokens', sa.Integer(), server_default='0', nullable=True),
            sa.Column('total_output_tokens', sa.Integer(), server_default='0', nullable=True),
            sa.Column('free_tokens_used', sa.Integer(), server_default='0', nullable=True),
            sa.Column('paid_tokens_used', sa.Integer(), server_default='0', nullable=True),
            sa.Column('total_spending', sa.Float(), server_default='0.0', nullable=True),
            sa.Column('spending_limit', sa.Float(), server_default='100.0', nullable=True),
            sa.Column('alert_threshold_reached', sa.Boolean(), server_default='0', nullable=True),
            sa.Column('alert_sent_at', sa.DateTime(), nullable=True),
            sa.Column('limit_reached', sa.Boolean(), server_default='0', nullable=True),
            sa.Column('limit_reached_at', sa.DateTime(), nullable=True),
            sa.Column('model_usage_breakdown', sa.Text(), nullable=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        )
    else:
        # Table existed (e.g. created by SQLModel create_all) — ensure all columns are present
        for col_name, col_def in [
            ('deleted_at', sa.Column('deleted_at', sa.DateTime(), nullable=True)),
            ('created_at', sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True)),
            ('updated_at', sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True)),
        ]:
            if not _column_exists('user_usage_summary', col_name):
                op.add_column('user_usage_summary', col_def)
    
    # Create index for faster lookups by user and billing period
    if not _index_exists('user_usage_summary', 'ix_user_usage_summary_user_id'):
        op.create_index('ix_user_usage_summary_user_id', 'user_usage_summary', ['user_id'])
    if not _index_exists('user_usage_summary', 'ix_user_usage_summary_billing_period'):
        op.create_index(
            'ix_user_usage_summary_billing_period', 
            'user_usage_summary', 
            ['user_id', 'billing_year', 'billing_month'],
            unique=True
        )


def downgrade() -> None:
    # Drop user_usage_summary table
    op.drop_index('ix_user_usage_summary_billing_period', table_name='user_usage_summary')
    op.drop_index('ix_user_usage_summary_user_id', table_name='user_usage_summary')
    op.drop_table('user_usage_summary')
    
    # Remove columns from user table
    op.drop_column('user', 'monthly_spending_alert_sent')
    op.drop_column('user', 'spending_limit')
