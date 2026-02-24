"""Add refresh_token table for JWT refresh token support

Revision ID: add_refresh_token_table
Revises: add_model_routing_to_provider
Create Date: 2025-01-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = "add_refresh_token_table"
down_revision: Union[str, None] = "add_model_routing_to_provider"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create refresh_token table for web mode JWT authentication."""
    op.create_table(
        "refresh_token",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("device_info", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("ip_address", sqlmodel.sql.sqltypes.AutoString(length=45), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes for efficient lookups
    op.create_index("ix_refresh_token_user_id", "refresh_token", ["user_id"])
    op.create_index("ix_refresh_token_token_hash", "refresh_token", ["token_hash"], unique=True)
    op.create_index("ix_refresh_token_expires_at", "refresh_token", ["expires_at"])


def downgrade() -> None:
    """Drop refresh_token table."""
    op.drop_index("ix_refresh_token_expires_at", table_name="refresh_token")
    op.drop_index("ix_refresh_token_token_hash", table_name="refresh_token")
    op.drop_index("ix_refresh_token_user_id", table_name="refresh_token")
    op.drop_table("refresh_token")
