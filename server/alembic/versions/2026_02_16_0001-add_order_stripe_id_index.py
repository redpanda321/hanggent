"""Add index/unique constraint for order.stripe_id

Revision ID: 2026_02_16_0001
Revises: 2026_02_15_0002
Create Date: 2026-02-16

This strengthens idempotency for Stripe checkout fulfillment by ensuring
`order.stripe_id` is indexed and (when safe) unique.

We make the migration defensive:
- If the `order` table doesn't exist, do nothing.
- If duplicates exist, create a non-unique index instead of failing deploy.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2026_02_16_0001"
down_revision: Union[str, None] = "2026_02_15_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(conn)
    for idx in inspector.get_indexes(table_name):
        if idx.get("name") == index_name:
            return True
    return False


def _has_duplicate_stripe_ids(conn) -> bool:
    # "order" is a reserved keyword; rely on SQLAlchemy text and quoting.
    # We only need to know if any duplicates exist.
    sql = sa.text(
        'SELECT stripe_id FROM "order" '
        'WHERE stripe_id IS NOT NULL AND stripe_id <> \'\' '
        'GROUP BY stripe_id HAVING COUNT(*) > 1 LIMIT 1'
    )
    row = conn.execute(sql).first()
    return row is not None


def upgrade() -> None:
    conn = op.get_bind()

    # If the order table doesn't exist yet, create it.
    if not _table_exists(conn, "order"):
        op.create_table(
            "order",
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("order_type", sa.SmallInteger(), nullable=True),
            sa.Column("price", sa.Integer(), server_default="0", nullable=False),
            sa.Column("status", sa.SmallInteger(), nullable=True),
            sa.Column("payment_method", sa.String(32), server_default="", nullable=False),
            sa.Column("stripe_id", sa.String(1024), nullable=False),
            sa.Column("third_party_id", sa.String(1024), nullable=True),
            sa.Column("plan_id", sa.Integer(), nullable=True),
            sa.Column("period", sa.String(16), nullable=True),
            sa.Column("buy_type", sa.Integer(), nullable=True),
            sa.Column("use_num", sa.Integer(), nullable=True),
            sa.Column("left_num", sa.Integer(), nullable=True),
            sa.Column("extra", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["plan_id"], ["plan.id"]),
        )
        op.create_index("ix_order_user_id", "order", ["user_id"], unique=False)

    unique_index_name = "ux_order_stripe_id"
    non_unique_index_name = "ix_order_stripe_id"

    # If a unique index already exists, nothing to do.
    if _index_exists(conn, "order", unique_index_name):
        return

    # If duplicates exist, create a non-unique index to at least speed up
    # idempotency lookups without failing migration.
    if _has_duplicate_stripe_ids(conn):
        if not _index_exists(conn, "order", non_unique_index_name):
            op.create_index(non_unique_index_name, "order", ["stripe_id"], unique=False)
        return

    # No duplicates: enforce uniqueness for true idempotency.
    op.create_index(unique_index_name, "order", ["stripe_id"], unique=True)


def downgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "order"):
        return

    unique_index_name = "ux_order_stripe_id"
    non_unique_index_name = "ix_order_stripe_id"

    # Drop whichever we created.
    if _index_exists(conn, "order", unique_index_name):
        op.drop_index(unique_index_name, table_name="order")
    if _index_exists(conn, "order", non_unique_index_name):
        op.drop_index(non_unique_index_name, table_name="order")
