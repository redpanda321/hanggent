"""add_stripe_fields_to_user

Revision ID: add_stripe_fields_to_user
Revises: add_clerk_id_to_user
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_stripe_fields_to_user'
down_revision: Union[str, None] = 'add_clerk_id_to_user'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Stripe payment fields to user table
    op.add_column('user', sa.Column('stripe_customer_id', sa.String(255), nullable=True))
    op.add_column('user', sa.Column('subscription_plan', sa.String(32), nullable=False, server_default='free'))
    op.add_column('user', sa.Column('stripe_subscription_id', sa.String(255), nullable=True))
    op.add_column('user', sa.Column('subscription_status', sa.String(64), nullable=True))
    op.add_column('user', sa.Column('subscription_period_end', sa.DateTime(), nullable=True))
    
    # Add index for stripe_customer_id for faster lookups
    op.create_index('ix_user_stripe_customer_id', 'user', ['stripe_customer_id'], unique=True)
    
    # Add index for subscription_plan for filtering users by plan
    op.create_index('ix_user_subscription_plan', 'user', ['subscription_plan'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_user_subscription_plan', table_name='user')
    op.drop_index('ix_user_stripe_customer_id', table_name='user')
    
    # Drop columns
    op.drop_column('user', 'subscription_period_end')
    op.drop_column('user', 'subscription_status')
    op.drop_column('user', 'stripe_subscription_id')
    op.drop_column('user', 'subscription_plan')
    op.drop_column('user', 'stripe_customer_id')
