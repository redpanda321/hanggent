"""Add channel_linking_code table for generic IM account linking

Revision ID: 2026_02_17_0002
Revises: 2026_02_17_0001
Create Date: 2026-02-17

Generic linking-code table that supports any IM channel, not just Telegram.
A 6-digit code is generated per user + channel; the user sends ``/link <CODE>``
in the IM app to create/update a ``ChannelUserMapping``.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "2026_02_17_0002"
down_revision = "2026_02_17_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_linking_code",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False, index=True),
        sa.Column("channel_type", sa.String(32), nullable=False, index=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("channel_linking_code")
