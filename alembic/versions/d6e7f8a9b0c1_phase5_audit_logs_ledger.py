"""Phase 5: Add immutable audit_logs ledger table

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-11-08 12:08:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "audit_logs" not in existing_tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "chat_id",
                sa.BigInteger(),
                sa.ForeignKey("chats.chat_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "actor_user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.user_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("target_type", sa.String(length=64), nullable=True),
            sa.Column("target_id", sa.String(length=64), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_audit_logs_chat_id", "audit_logs", ["chat_id"], unique=False)
        op.create_index(
            "ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"], unique=False
        )
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
        op.create_index(
            "ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "audit_logs" in existing_tables:
        op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
        op.drop_index("ix_audit_logs_action", table_name="audit_logs")
        op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
        op.drop_index("ix_audit_logs_chat_id", table_name="audit_logs")
        op.drop_table("audit_logs")
