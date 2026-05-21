"""fix_chats_table

Revision ID: a1b2c3d4e5f6
Revises: 7ccedbcb9131
Create Date: 2026-03-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '7ccedbcb9131'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Ensure chats table exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id BIGINT PRIMARY KEY,
            title VARCHAR NOT NULL,
            channel_id BIGINT,
            admin_chat_id BIGINT
        )
    """)
    op.create_index(op.f('ix_chats_chat_id'), 'chats', ['chat_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_chats_chat_id'), table_name='chats')
    op.drop_table('chats')
