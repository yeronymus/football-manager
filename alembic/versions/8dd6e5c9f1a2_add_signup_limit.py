"""Add signup limit and main players count

Revision ID: 8dd6e5c9f1a2
Revises: 7ccedbcb9131
Create Date: 2026-03-24 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8dd6e5c9f1a2'
down_revision: Union[str, Sequence[str], None] = '7ccedbcb9131'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add columns to games table
    op.add_column('games', sa.Column('signup_limit', sa.Integer(), nullable=True, server_default='999'))
    op.add_column('games', sa.Column('main_players_count', sa.Integer(), nullable=True, server_default='22'))

def downgrade() -> None:
    op.drop_column('games', 'main_players_count')
    op.drop_column('games', 'signup_limit')
