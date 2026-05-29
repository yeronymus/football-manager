"""merge heads

Revision ID: 6188cf2be66f
Revises: a7b8c9d0e1f2, f2a3b4c5d6e7
Create Date: 2026-05-26 14:29:53.542058

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6188cf2be66f'
down_revision: Union[str, Sequence[str], None] = ('a7b8c9d0e1f2', 'f2a3b4c5d6e7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
