"""add_performance_indexes

Revision ID: e5f4a3b2c1d0
Revises: 1706a4d5b1c2
Create Date: 2026-05-13 12:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f4a3b2c1d0'
down_revision: Union[str, Sequence[str], None] = '1706a4d5b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add indexes for ChatAdmin
    op.create_index(op.f('ix_chat_admins_chat_id'), 'chat_admins', ['chat_id'], unique=False)
    op.create_index(op.f('ix_chat_admins_user_id'), 'chat_admins', ['user_id'], unique=False)
    
    # Add index for Game
    op.create_index(op.f('ix_games_chat_id'), 'games', ['chat_id'], unique=False)
    
    # Add indexes for PlayerProfile
    op.create_index(op.f('ix_player_profiles_chat_id'), 'player_profiles', ['chat_id'], unique=False)
    op.create_index(op.f('ix_player_profiles_user_id'), 'player_profiles', ['user_id'], unique=False)
    
    # Add indexes for Signup
    op.create_index(op.f('ix_signups_game_id'), 'signups', ['game_id'], unique=False)
    op.create_index(op.f('ix_signups_user_id'), 'signups', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_signups_user_id'), table_name='signups')
    op.drop_index(op.f('ix_signups_game_id'), table_name='signups')
    op.drop_index(op.f('ix_player_profiles_user_id'), table_name='player_profiles')
    op.drop_index(op.f('ix_player_profiles_chat_id'), table_name='player_profiles')
    op.drop_index(op.f('ix_games_chat_id'), table_name='games')
    op.drop_index(op.f('ix_chat_admins_user_id'), table_name='chat_admins')
    op.drop_index(op.f('ix_chat_admins_chat_id'), table_name='chat_admins')
