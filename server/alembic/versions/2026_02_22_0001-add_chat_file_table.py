"""Add chat_file table for project file uploads

Revision ID: 2026_02_22_0001
Revises: 2026_02_20_0001
Create Date: 2026-02-22

Stores metadata (filename, size, MIME type, storage path, public URL)
for files uploaded to chat projects.  Actual file bytes live on disk
under PUBLIC_DIR/files/<user_id>/<task_id>/.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2026_02_22_0001"
down_revision: Union[str, None] = "2026_02_20_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_file",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("task_id", sa.String(255), nullable=False, index=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mime_type", sa.String(255), nullable=False, server_default="application/octet-stream"),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("chat_file")
