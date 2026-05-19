"""add voting_message_id

Revision ID: f6f5e4d3c2b1
Revises: e5f4a3b2c1d0
Create Date: 2026-05-17 18:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6f5e4d3c2b1'
down_revision: Union[str, Sequence[str], None] = 'e5f4a3b2c1d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('games', sa.Column('voting_message_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('games', 'voting_message_id')
