"""Add admin_settings table with default additional_fee_percent

Revision ID: 2026_02_18_0001
Revises: 2026_02_17_0002
Create Date: 2026-02-18

Creates a generic key-value admin_settings table and seeds the default
additional_fee_percent = 5  (5 % markup on base model token costs).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# revision identifiers, used by Alembic.
revision: str = "2026_02_18_0001"
down_revision: Union[str, None] = "2026_02_17_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("admin_settings"):
        return

    op.create_table(
        "admin_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=True, server_default=""),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed the default additional fee
    op.execute(
        sa.text(
            "INSERT INTO admin_settings (key, value, description, created_at, updated_at) "
            "VALUES ('additional_fee_percent', '5', "
            "'Percentage fee added on top of base model token costs for cloud models', now(), now())"
        )
    )


def downgrade() -> None:
    op.drop_table("admin_settings")
