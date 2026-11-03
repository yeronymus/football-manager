"""Add tenant policy, billing_mode, currency, timezone, sport_type and English default

Revision ID: 9c1d2e3f4a5b
Revises: 8b9c0d1e2f3a
Create Date: 2026-11-03 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "9c1d2e3f4a5b"
down_revision: Union[str, Sequence[str], None] = "8b9c0d1e2f3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("chats")}

    if "currency" not in existing_cols:
        op.add_column(
            "chats",
            sa.Column("currency", sa.String(length=8), nullable=False, server_default="CZK"),
        )
    if "timezone" not in existing_cols:
        op.add_column(
            "chats",
            sa.Column(
                "timezone",
                sa.String(length=64),
                nullable=False,
                server_default="Europe/Prague",
            ),
        )
    if "sport_type" not in existing_cols:
        op.add_column(
            "chats",
            sa.Column(
                "sport_type",
                sa.String(length=32),
                nullable=False,
                server_default="football",
            ),
        )
    if "billing_mode" not in existing_cols:
        op.add_column(
            "chats",
            sa.Column(
                "billing_mode",
                sa.String(length=32),
                nullable=False,
                server_default="manual",
            ),
        )
    if "policy" not in existing_cols:
        op.add_column(
            "chats",
            sa.Column("policy", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("chats")}

    for col_name in ("policy", "billing_mode", "sport_type", "timezone", "currency"):
        if col_name in existing_cols:
            op.drop_column("chats", col_name)
