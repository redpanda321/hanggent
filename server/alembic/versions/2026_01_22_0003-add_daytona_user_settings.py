"""Add user_daytona_settings and user_sandbox_session tables

Revision ID: add_daytona_user_settings
Revises: add_refresh_token_table
Create Date: 2026-01-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = "add_daytona_user_settings"
down_revision: Union[str, None] = "add_refresh_token_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_daytona_settings and user_sandbox_session tables."""
    
    # Create user_daytona_settings table
    op.create_table(
        "user_daytona_settings",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_api_key", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column("server_url", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False, server_default="https://app.daytona.io"),
        sa.Column("target", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False, server_default="us"),
        sa.Column("cpu_limit", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("memory_limit_gb", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("disk_limit_gb", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("auto_stop_interval", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("auto_archive_interval", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("sandbox_image", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("vnc_password", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uix_user_daytona_settings_user_id"),
    )
    op.create_index("ix_user_daytona_settings_user_id", "user_daytona_settings", ["user_id"])
    
    # Create user_sandbox_session table
    op.create_table(
        "user_sandbox_session",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sandbox_id", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("daytona_sandbox_id", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        sa.Column("chat_session_id", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False, server_default="creating"),
        sa.Column("vnc_url", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column("browser_api_url", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column("workspace_path", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True, server_default="/workspace"),
        sa.Column("last_activity_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("cpu_allocated", sa.Integer(), nullable=True),
        sa.Column("memory_allocated_gb", sa.Integer(), nullable=True),
        sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_sandbox_session_user_id", "user_sandbox_session", ["user_id"])
    op.create_index("ix_user_sandbox_session_sandbox_id", "user_sandbox_session", ["sandbox_id"])
    op.create_index("ix_user_sandbox_session_chat_session_id", "user_sandbox_session", ["chat_session_id"])
    op.create_index("ix_sandbox_session_user_status", "user_sandbox_session", ["user_id", "status"])
    op.create_index("ix_sandbox_session_daytona_id", "user_sandbox_session", ["daytona_sandbox_id"])


def downgrade() -> None:
    """Drop user_daytona_settings and user_sandbox_session tables."""
    # Drop user_sandbox_session indexes and table
    op.drop_index("ix_sandbox_session_daytona_id", table_name="user_sandbox_session")
    op.drop_index("ix_sandbox_session_user_status", table_name="user_sandbox_session")
    op.drop_index("ix_user_sandbox_session_chat_session_id", table_name="user_sandbox_session")
    op.drop_index("ix_user_sandbox_session_sandbox_id", table_name="user_sandbox_session")
    op.drop_index("ix_user_sandbox_session_user_id", table_name="user_sandbox_session")
    op.drop_table("user_sandbox_session")
    
    # Drop user_daytona_settings indexes and table
    op.drop_index("ix_user_daytona_settings_user_id", table_name="user_daytona_settings")
    op.drop_table("user_daytona_settings")
