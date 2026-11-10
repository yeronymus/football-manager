"""Add chat_members table for tracking group participants and outreach

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-11-10 01:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "chat_members" not in existing_tables:
        op.create_table(
            "chat_members",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column(
                "chat_id",
                sa.BigInteger(),
                sa.ForeignKey("chats.chat_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("username", sa.String(), nullable=True),
            sa.Column("full_name", sa.String(), nullable=True),
            sa.Column("status", sa.String(length=32), server_default="member", nullable=False),
            sa.Column("is_registered", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column(
                "first_seen_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("chat_id", "user_id", name="uq_chat_members_chat_user"),
        )
        op.create_index("ix_chat_members_id", "chat_members", ["id"])
        op.create_index("ix_chat_members_chat_id", "chat_members", ["chat_id"])
        op.create_index("ix_chat_members_user_id", "chat_members", ["user_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "chat_members" in existing_tables:
        op.drop_index("ix_chat_members_user_id", table_name="chat_members")
        op.drop_index("ix_chat_members_chat_id", table_name="chat_members")
        op.drop_index("ix_chat_members_id", table_name="chat_members")
        op.drop_table("chat_members")
