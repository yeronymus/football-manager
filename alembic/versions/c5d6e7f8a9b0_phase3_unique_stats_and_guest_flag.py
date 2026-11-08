"""Add is_guest to users and unique (game_id, user_id) constraints on game_stats and rating_history

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-11-08 11:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Add is_guest column to users and backfill negative user_ids
    user_cols = {col["name"] for col in inspector.get_columns("users")}
    if "is_guest" not in user_cols:
        op.add_column(
            "users",
            sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        op.execute(sa.text("UPDATE users SET is_guest = true WHERE user_id < 0"))

    # 2. Deduplicate any legacy duplicate (game_id, user_id) rows before adding UniqueConstraints
    op.execute(
        sa.text(
            """
            DELETE FROM game_stats
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM game_stats
                GROUP BY game_id, user_id
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM rating_history
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM rating_history
                GROUP BY game_id, user_id
            )
            """
        )
    )

    gs_uniques = {u["name"] for u in inspector.get_unique_constraints("game_stats")}
    if "uq_game_stats_game_user" not in gs_uniques:
        with op.batch_alter_table("game_stats") as batch_op:
            batch_op.create_unique_constraint("uq_game_stats_game_user", ["game_id", "user_id"])

    rh_uniques = {u["name"] for u in inspector.get_unique_constraints("rating_history")}
    if "uq_rating_history_game_user" not in rh_uniques:
        with op.batch_alter_table("rating_history") as batch_op:
            batch_op.create_unique_constraint("uq_rating_history_game_user", ["game_id", "user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    rh_uniques = {u["name"] for u in inspector.get_unique_constraints("rating_history")}
    if "uq_rating_history_game_user" in rh_uniques:
        with op.batch_alter_table("rating_history") as batch_op:
            batch_op.drop_constraint("uq_rating_history_game_user", type_="unique")

    gs_uniques = {u["name"] for u in inspector.get_unique_constraints("game_stats")}
    if "uq_game_stats_game_user" in gs_uniques:
        with op.batch_alter_table("game_stats") as batch_op:
            batch_op.drop_constraint("uq_game_stats_game_user", type_="unique")

    user_cols = {col["name"] for col in inspector.get_columns("users")}
    if "is_guest" in user_cols:
        op.drop_column("users", "is_guest")
