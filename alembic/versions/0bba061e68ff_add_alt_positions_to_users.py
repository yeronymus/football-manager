"""add alt positions to users

Revision ID: 0bba061e68ff
Revises: f6f5e4d3c2b1
Create Date: 2026-05-20 09:09:40.877369

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bba061e68ff'
down_revision: Union[str, Sequence[str], None] = 'f6f5e4d3c2b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('alt_positions', sa.ARRAY(sa.String()), nullable=True, server_default='{}'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'alt_positions')
