"""Add sequence_number to games table for O(1) per-tenant match numbering

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-11-08 11:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    game_cols = {col["name"] for col in inspector.get_columns("games")}

    if "sequence_number" not in game_cols:
        op.add_column(
            "games",
            sa.Column("sequence_number", sa.Integer(), nullable=True),
        )
        op.create_index(
            op.f("ix_games_sequence_number"),
            "games",
            ["sequence_number"],
            unique=False,
        )
        # Backfill sequential 1-based match numbers per chat_id for non-cancelled games
        op.execute(
            sa.text(
                """
                WITH numbered AS (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY chat_id
                               ORDER BY id ASC
                           ) AS seq_num
                    FROM games
                    WHERE status != 'CANCELLED' OR status IS NULL
                )
                UPDATE games
                SET sequence_number = numbered.seq_num
                FROM numbered
                WHERE games.id = numbered.id
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    game_cols = {col["name"] for col in inspector.get_columns("games")}

    if "sequence_number" in game_cols:
        op.drop_index(op.f("ix_games_sequence_number"), table_name="games")
        op.drop_column("games", "sequence_number")
