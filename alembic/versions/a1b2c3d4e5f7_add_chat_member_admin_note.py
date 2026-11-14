"""Add admin_note column to chat_members

Revision ID: a1b2c3d4e5f7
Revises: f1a2b3c4d5e6
Create Date: 2026-11-14 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "chat_members" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("chat_members")]
        if "admin_note" not in columns:
            op.add_column(
                "chat_members",
                sa.Column("admin_note", sa.Text(), nullable=True),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "chat_members" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("chat_members")]
        if "admin_note" in columns:
            op.drop_column("chat_members", "admin_note")
