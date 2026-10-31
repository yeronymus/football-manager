"""Add player_cards table

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-10-31 18:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b9c0d1e2f3a'
down_revision: Union[str, Sequence[str], None] = '7a8b9c0d1e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create player_cards table
    op.create_table(
        'player_cards',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('card_type', sa.String(length=10), nullable=False),
        sa.Column('weeks', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('issued_by', sa.BigInteger(), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.chat_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['issued_by'], ['users.user_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_player_cards_id'), 'player_cards', ['id'], unique=False)
    op.create_index(op.f('ix_player_cards_user_id'), 'player_cards', ['user_id'], unique=False)
    op.create_index(op.f('ix_player_cards_chat_id'), 'player_cards', ['chat_id'], unique=False)
    op.create_index(op.f('ix_player_cards_is_active'), 'player_cards', ['is_active'], unique=False)
    op.create_index('ix_player_cards_lookup', 'player_cards', ['user_id', 'chat_id', 'is_active'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_player_cards_lookup', table_name='player_cards')
    op.drop_index(op.f('ix_player_cards_is_active'), table_name='player_cards')
    op.drop_index(op.f('ix_player_cards_chat_id'), table_name='player_cards')
    op.drop_index(op.f('ix_player_cards_user_id'), table_name='player_cards')
    op.drop_index(op.f('ix_player_cards_id'), table_name='player_cards')
    op.drop_table('player_cards')
