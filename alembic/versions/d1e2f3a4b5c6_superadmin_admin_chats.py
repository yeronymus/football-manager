"""superadmin_admin_chats

Revision ID: d1e2f3a4b5c6
Revises: cab7ed4fc677
Create Date: 2026-05-01 22:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'cab7ed4fc677'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_superadmin to users table
    op.add_column('users', sa.Column('is_superadmin', sa.Boolean(), server_default='false', nullable=True))
    
    # Remove admin_chat_id from chats table
    op.drop_column('chats', 'admin_chat_id')


def downgrade() -> None:
    # Add admin_chat_id back
    op.add_column('chats', sa.Column('admin_chat_id', sa.BigInteger(), nullable=True))
    
    # Remove is_superadmin
    op.drop_column('users', 'is_superadmin')
