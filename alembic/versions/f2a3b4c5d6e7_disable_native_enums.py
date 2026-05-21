"""disable_native_enums

Revision ID: f2a3b4c5d6e7
Revises: e1a2b3c4d5e6
Create Date: 2026-05-20 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f2a3b4c5d6e7'
down_revision = 'e1a2b3c4d5e6'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # No changes needed to the actual table columns if they were already VARCHAR or if we want them to behave as VARCHAR.
    # This migration is primarily to keep alembic history in sync with the model changes.
    # However, to be safe, we can explicitly alter columns to VARCHAR if they were native enums.
    
    # List of columns that were Enums
    # users.player_position
    # chats.language
    # games.status, games.game_type, games.winner_team
    # signups.status, signups.team, signups.position
    # votes.vote_team
    
    # We use 'USING column_name::text' to safely convert from potential native enums to varchar
    op.execute("ALTER TABLE users ALTER COLUMN player_position TYPE VARCHAR USING player_position::text")
    op.execute("ALTER TABLE chats ALTER COLUMN language TYPE VARCHAR USING language::text")
    op.execute("ALTER TABLE games ALTER COLUMN status TYPE VARCHAR USING status::text")
    op.execute("ALTER TABLE games ALTER COLUMN game_type TYPE VARCHAR USING game_type::text")
    op.execute("ALTER TABLE games ALTER COLUMN winner_team TYPE VARCHAR USING winner_team::text")
    op.execute("ALTER TABLE signups ALTER COLUMN status TYPE VARCHAR USING status::text")
    op.execute("ALTER TABLE signups ALTER COLUMN team TYPE VARCHAR USING team::text")
    op.execute("ALTER TABLE signups ALTER COLUMN position TYPE VARCHAR USING position::text")
    op.execute("ALTER TABLE votes ALTER COLUMN vote_team TYPE VARCHAR USING vote_team::text")

def downgrade() -> None:
    pass
