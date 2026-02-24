"""Add invite_code column to user table

Stores a unique referral code per user, generated lazily on first request.

Revision ID: 2026_02_15_0002
Revises: 2026_02_15_0001
Create Date: 2026-02-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2026_02_15_0002'
down_revision: Union[str, None] = '2026_02_15_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user',
        sa.Column('invite_code', sa.String(32), nullable=True, unique=True),
    )


def downgrade() -> None:
    op.drop_column('user', 'invite_code')
