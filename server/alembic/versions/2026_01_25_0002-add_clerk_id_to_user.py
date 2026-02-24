"""add_clerk_id_to_user

Revision ID: add_clerk_id_to_user
Revises: add_usage_record_table
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_clerk_id_to_user'
down_revision: Union[str, None] = 'add_usage_record_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add clerk_id column to user table
    op.add_column('user', sa.Column('clerk_id', sa.String(255), nullable=True))
    
    # Add unique index for clerk_id
    op.create_index('ix_user_clerk_id', 'user', ['clerk_id'], unique=True)


def downgrade() -> None:
    # Drop unique index
    op.drop_index('ix_user_clerk_id', table_name='user')
    
    # Drop clerk_id column
    op.drop_column('user', 'clerk_id')
