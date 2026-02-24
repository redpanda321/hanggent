"""Widen chat_history project_name to VARCHAR(512) and summary to TEXT

Revision ID: 2026_02_20_0001
Revises: 2026_02_18_0001
Create Date: 2026-02-20

The project_name column was VARCHAR(128) which is too short for AI-generated
summaries that may include <think> blocks. Widen to VARCHAR(512).
The summary column was VARCHAR(1024) which can also be exceeded. Change to TEXT.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2026_02_20_0001"
down_revision: Union[str, None] = "2026_02_18_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "chat_history",
        "project_name",
        existing_type=sa.String(128),
        type_=sa.String(512),
        existing_nullable=True,
    )
    op.alter_column(
        "chat_history",
        "summary",
        existing_type=sa.String(1024),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "chat_history",
        "summary",
        existing_type=sa.Text(),
        type_=sa.String(1024),
        existing_nullable=True,
    )
    op.alter_column(
        "chat_history",
        "project_name",
        existing_type=sa.String(512),
        type_=sa.String(128),
        existing_nullable=True,
    )
