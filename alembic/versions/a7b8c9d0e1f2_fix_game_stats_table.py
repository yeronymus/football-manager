"""fix_game_stats_table

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-11 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Ensure game_stats table exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS game_stats (
            id SERIAL PRIMARY KEY,
            game_id INTEGER NOT NULL REFERENCES games(id),
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            goals INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            is_mvp BOOLEAN DEFAULT FALSE
        )
    """)
    op.create_index(op.f('ix_game_stats_id'), 'game_stats', ['id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_game_stats_id'), table_name='game_stats')
    op.drop_table('game_stats')
