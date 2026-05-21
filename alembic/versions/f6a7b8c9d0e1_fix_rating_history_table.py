"""fix_rating_history_table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-10 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Ensure rating_history table exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS rating_history (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            game_id INTEGER NOT NULL REFERENCES games(id),
            old_rating INTEGER NOT NULL,
            new_rating INTEGER NOT NULL,
            change INTEGER NOT NULL,
            date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.create_index(op.f('ix_rating_history_id'), 'rating_history', ['id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_rating_history_id'), table_name='rating_history')
    op.drop_table('rating_history')
