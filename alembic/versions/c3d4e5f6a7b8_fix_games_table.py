"""fix_games_table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-07 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Ensure games table exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL REFERENCES chats(chat_id),
            created_by BIGINT NOT NULL REFERENCES users(user_id),
            date_time TIMESTAMP WITH TIME ZONE NOT NULL,
            location VARCHAR NOT NULL,
            max_players INTEGER DEFAULT 18,
            price INTEGER DEFAULT 100,
            payment_info VARCHAR DEFAULT '2924402033/0800',
            team_count INTEGER DEFAULT 2,
            gk_hours INTEGER DEFAULT 48,
            duration FLOAT DEFAULT 2.0,
            status VARCHAR DEFAULT 'open',
            game_type VARCHAR DEFAULT 'regular',
            winner_team VARCHAR,
            score_a INTEGER,
            score_b INTEGER,
            score_c INTEGER,
            message_id BIGINT,
            channel_id BIGINT,
            channel_message_id BIGINT,
            admin_message_id BIGINT,
            has_active_gk_a BOOLEAN DEFAULT TRUE,
            has_active_gk_b BOOLEAN DEFAULT TRUE,
            has_active_gk_c BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            registration_hours INTEGER DEFAULT 0
        )
    """)
    op.create_index(op.f('ix_games_id'), 'games', ['id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_games_id'), table_name='games')
    op.drop_table('games')
