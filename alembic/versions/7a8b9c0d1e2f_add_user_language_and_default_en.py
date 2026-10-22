"""Add user language and update default chat language to en

Revision ID: 7a8b9c0d1e2f
Revises: 6188cf2be66f
Create Date: 2026-10-22 17:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, Sequence[str], None] = '6188cf2be66f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add language column to users table (default 'en')
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR DEFAULT 'en'"))
    
    # 2. Update default for chats.language to 'en'
    op.execute(sa.text("ALTER TABLE chats ALTER COLUMN language SET DEFAULT 'en'"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE chats ALTER COLUMN language SET DEFAULT 'ru'"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS language"))
