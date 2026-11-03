"""Add is_late to signups and create inventory_items table

Revision ID: a3b4c5d6e7f8
Revises: 9c1d2e3f4a5b
Create Date: 2026-11-03 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "9c1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Add is_late to signups if not present
    signup_cols = {col["name"] for col in inspector.get_columns("signups")}
    if "is_late" not in signup_cols:
        op.add_column(
            "signups",
            sa.Column("is_late", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    # 2. Create inventory_items table if not exists
    tables = inspector.get_table_names()
    if "inventory_items" not in tables:
        op.create_table(
            "inventory_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("chat_id", sa.BigInteger(), sa.ForeignKey("chats.chat_id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("category", sa.String(length=32), nullable=False, server_default="OTHER"),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="IN_STOCK"),
            sa.Column("purchase_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("lifespan_days", sa.Integer(), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("alert_recipient_user_id", sa.BigInteger(), nullable=True),
            sa.Column("last_alert_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    tables = inspector.get_table_names()
    if "inventory_items" in tables:
        op.drop_table("inventory_items")

    signup_cols = {col["name"] for col in inspector.get_columns("signups")}
    if "is_late" in signup_cols:
        op.drop_column("signups", "is_late")
