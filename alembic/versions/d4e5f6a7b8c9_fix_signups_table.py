"""fix_signups_table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-08 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Ensure signups table exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS signups (
            id SERIAL PRIMARY KEY,
            game_id INTEGER NOT NULL REFERENCES games(id),
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            status VARCHAR DEFAULT 'active',
            team VARCHAR,
            position VARCHAR,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            is_paid BOOLEAN DEFAULT FALSE,
            UNIQUE(game_id, user_id)
        )
    """)
    op.create_index(op.f('ix_signups_id'), 'signups', ['id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_signups_id'), table_name='signups')
    op.drop_table('signups')
