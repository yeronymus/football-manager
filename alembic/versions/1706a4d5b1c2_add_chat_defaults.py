"""add_chat_defaults

Revision ID: 1706a4d5b1c2
Revises: d1e2f3a4b5c6
Create Date: 2026-05-03 12:34:32.235482

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1706a4d5b1c2'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chats', sa.Column('default_location', sa.String(), nullable=True))
    op.add_column('chats', sa.Column('default_price', sa.Integer(), server_default='155'))
    op.add_column('chats', sa.Column('default_team_count', sa.Integer(), server_default='2'))
    op.add_column('chats', sa.Column('default_max_players', sa.Integer(), server_default='26'))
    op.add_column('chats', sa.Column('default_main_players_count', sa.Integer(), server_default='22'))
    op.add_column('chats', sa.Column('default_duration', sa.Float(), server_default='2.0'))
    op.add_column('chats', sa.Column('default_gk_hours', sa.Integer(), server_default='0'))
    op.add_column('chats', sa.Column('default_registration_hours', sa.Integer(), server_default='24'))
    op.add_column('chats', sa.Column('default_signup_limit', sa.Integer(), server_default='40'))


def downgrade() -> None:
    op.drop_column('chats', 'default_signup_limit')
    op.drop_column('chats', 'default_registration_hours')
    op.drop_column('chats', 'default_gk_hours')
    op.drop_column('chats', 'default_duration')
    op.drop_column('chats', 'default_main_players_count')
    op.drop_column('chats', 'default_max_players')
    op.drop_column('chats', 'default_team_count')
    op.drop_column('chats', 'default_price')
    op.drop_column('chats', 'default_location')
