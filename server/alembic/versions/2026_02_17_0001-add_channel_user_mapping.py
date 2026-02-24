"""Add channel_user_mapping table for generic IM auto-registration

Revision ID: 2026_02_17_0001
Revises: 2026_02_16_0001
Create Date: 2026-02-17

Introduces a generic ``channel_user_mapping`` table that maps any IM
channel identity (Telegram, Discord, Slack, WhatsApp, LINE, Feishu, …)
to a Hanggent user.  This replaces the Telegram-only
``telegram_user_mapping`` for new registrations while keeping the old
table for backward compatibility.

Also migrates existing ``telegram_user_mapping`` rows into the new table.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2026_02_17_0001"
down_revision: Union[str, None] = "2026_02_16_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "channel_user_mapping"):
        op.create_table(
            "channel_user_mapping",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False, index=True),
            sa.Column("channel_type", sa.String(32), nullable=False, index=True),
            sa.Column("channel_user_id", sa.String(128), nullable=False, index=True),
            sa.Column("channel_username", sa.String(128), nullable=True),
            sa.Column("channel_metadata", sa.JSON(), nullable=True),
            sa.Column("auto_registered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("linked_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.TIMESTAMP(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("channel_type", "channel_user_id", name="uq_channel_identity"),
        )

    # Migrate existing telegram_user_mapping rows
    if _table_exists(conn, "telegram_user_mapping") and _table_exists(conn, "channel_user_mapping"):
        dialect = conn.dialect.name
        if dialect == "postgresql":
            conn.execute(
                sa.text("""
                    INSERT INTO channel_user_mapping
                        (user_id, channel_type, channel_user_id, channel_username,
                         auto_registered, linked_at, created_at, updated_at)
                    SELECT
                        user_id,
                        'telegram',
                        CAST(telegram_chat_id AS TEXT),
                        telegram_username,
                        false,
                        linked_at,
                        created_at,
                        updated_at
                    FROM telegram_user_mapping
                    WHERE deleted_at IS NULL
                    ON CONFLICT (channel_type, channel_user_id) DO UPDATE
                        SET updated_at = EXCLUDED.updated_at
                """)
            )
        else:
            conn.execute(
                sa.text("""
                    INSERT INTO channel_user_mapping
                        (user_id, channel_type, channel_user_id, channel_username,
                         auto_registered, linked_at, created_at, updated_at)
                    SELECT
                        user_id,
                        'telegram',
                        CAST(telegram_chat_id AS CHAR),
                        telegram_username,
                        0,
                        linked_at,
                        created_at,
                        updated_at
                    FROM telegram_user_mapping
                    WHERE deleted_at IS NULL
                    ON DUPLICATE KEY UPDATE updated_at = VALUES(updated_at)
                """)
            )


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "channel_user_mapping"):
        op.drop_table("channel_user_mapping")
