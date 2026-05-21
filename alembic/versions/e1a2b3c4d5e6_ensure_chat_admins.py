"""ensure_chat_admins

Revision ID: e1a2b3c4d5e6
Revises: 0bba061e68ff
Create Date: 2026-05-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e1a2b3c4d5e6'
down_revision = '0bba061e68ff'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Ensure chat_admins table exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS chat_admins (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL REFERENCES chats(chat_id),
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            can_edit_settings BOOLEAN DEFAULT TRUE,
            can_manage_games BOOLEAN DEFAULT TRUE,
            UNIQUE(chat_id, user_id)
        )
    """)
    # Ensure indexes exist (if not already created by e5f4a3b2c1d0)
    op.execute("CREATE INDEX IF NOT EXISTS ix_chat_admins_chat_id ON chat_admins (chat_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chat_admins_user_id ON chat_admins (user_id)")

def downgrade() -> None:
    pass
