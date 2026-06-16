"""fix_votes_table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Ensure votes table exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id SERIAL PRIMARY KEY,
            game_id INTEGER NOT NULL REFERENCES games(id),
            voter_id BIGINT NOT NULL REFERENCES users(user_id),
            target_id BIGINT NOT NULL REFERENCES users(user_id),
            vote_team VARCHAR NOT NULL,
            UNIQUE(game_id, voter_id, vote_team)
        )
    """)
    op.create_index(op.f('ix_votes_id'), 'votes', ['id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_votes_id'), table_name='votes')
    op.drop_table('votes')
