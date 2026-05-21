"""fix_users_table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-06 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Ensure users table exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username VARCHAR,
            full_name VARCHAR NOT NULL,
            player_position VARCHAR NOT NULL,
            stats_matches INTEGER DEFAULT 0,
            stats_mvp INTEGER DEFAULT 0,
            rating INTEGER DEFAULT 100,
            games_played INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.create_index(op.f('ix_users_user_id'), 'users', ['user_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_users_user_id'), table_name='users')
    op.drop_table('users')
