"""Change user.credits column from Integer to Float

Credits now store dollar amounts (e.g. 9.99 for a Plus subscription)
instead of integer token counts.

Revision ID: 2026_02_15_0001
Revises: 2026_02_12_0001
Create Date: 2026-02-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2026_02_15_0001'
down_revision: Union[str, None] = '2026_02_12_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter the credits column from Integer to Float.
    # Existing integer values (0, 5, 10 …) are valid floats — no data loss.
    op.alter_column(
        'user',
        'credits',
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_server_default=sa.text("0"),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'user',
        'credits',
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_server_default=sa.text("0"),
        existing_nullable=True,
    )
