"""Enable PostgreSQL Row-Level Security (RLS) policies on tenant-scoped tables

Revision ID: a2b3c4d5e6f7
Revises: b7c8d9e0f1a2
Create Date: 2026-11-14 11:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db.rls import generate_rls_policies_sql

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RLS_TABLES = ["games", "player_profiles", "chat_members", "player_cards", "inventory_items"]


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    for tbl in _RLS_TABLES:
        if tbl in existing_tables:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{tbl} ON {tbl};")

    for stmt in generate_rls_policies_sql():
        # Only execute statements for tables that exist in the current DB
        if any(f" {tbl}" in stmt or f"ON {tbl}" in stmt for tbl in existing_tables):
            op.execute(stmt)


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    for tbl in _RLS_TABLES:
        if tbl in existing_tables:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{tbl} ON {tbl};")
            op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")
