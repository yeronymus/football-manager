"""Add new positions to enums

Revision ID: ba3d7e5c9f5f
Revises: 9e1c2d3b4a5f
Create Date: 2026-04-25 11:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba3d7e5c9f5f'
down_revision: Union[str, Sequence[str], None] = '9e1c2d3b4a5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    new_positions = ['DEF', 'MID', 'LWB', 'RWB', 'ST', 'CF']
    
    # PostgreSQL requirement: ALTER TYPE ADD VALUE cannot run inside a transaction block
    with op.get_context().autocommit_block():
        for pos in new_positions:
            op.execute(sa.text(f"ALTER TYPE user_position ADD VALUE IF NOT EXISTS '{pos}'"))
            op.execute(sa.text(f"ALTER TYPE signup_position_enum ADD VALUE IF NOT EXISTS '{pos}'"))


def downgrade() -> None:
    # PostgreSQL doesn't support removing values from an ENUM easily.
    # Usually, we leave them as is or recreate the type (complex).
    pass
