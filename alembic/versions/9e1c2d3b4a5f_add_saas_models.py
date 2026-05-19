"""Add SaaS models PlayerProfile and AdBanner

Revision ID: 9e1c2d3b4a5f
Revises: 8dd6e5c9f1a2
Create Date: 2026-04-21 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e1c2d3b4a5f'
down_revision: Union[str, Sequence[str], None] = '8dd6e5c9f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns to "chats" table
    op.add_column('chats', sa.Column('language', sa.String(), nullable=True, server_default='ru'))
    op.add_column('chats', sa.Column('payment_info', sa.String(), nullable=True))
    op.add_column('chats', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))

    # 2. Create "player_profiles" table
    op.create_table('player_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('games_played', sa.Integer(), nullable=True),
        sa.Column('stats_matches', sa.Integer(), nullable=True),
        sa.Column('stats_mvp', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.chat_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'chat_id', name='unique_group_profile')
    )
    op.create_index(op.f('ix_player_profiles_id'), 'player_profiles', ['id'], unique=False)

    # 3. Create "ad_banners" table
    op.create_table('ad_banners',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.BigInteger(), nullable=True),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('link', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('show_probability', sa.Integer(), nullable=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.chat_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ad_banners_id'), 'ad_banners', ['id'], unique=False)

    # 4. Data Migration
    # We populate player_profiles for each user with their stats in their main chat.
    # Without this, switching to the new DB format would drop existing users' ELO.
    op.execute("""
        INSERT INTO player_profiles (user_id, chat_id, rating, games_played, stats_matches, stats_mvp)
        SELECT 
            u.user_id,
            COALESCE(
                (SELECT chat_id FROM signups s JOIN games g ON s.game_id = g.id WHERE s.user_id = u.user_id ORDER BY g.created_at DESC LIMIT 1),
                (SELECT chat_id FROM chats LIMIT 1)
            ),
            u.rating, u.games_played, u.stats_matches, u.stats_mvp
        FROM users u
        WHERE EXISTS (SELECT 1 FROM chats)
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    # 1. Drop ad banners
    op.drop_index(op.f('ix_ad_banners_id'), table_name='ad_banners')
    op.drop_table('ad_banners')

    # 2. Drop player profiles
    op.drop_index(op.f('ix_player_profiles_id'), table_name='player_profiles')
    op.drop_table('player_profiles')

    # 3. Drop columns from chats
    op.drop_column('chats', 'is_active')
    op.drop_column('chats', 'payment_info')
    op.drop_column('chats', 'language')
