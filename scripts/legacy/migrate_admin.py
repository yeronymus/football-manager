
import asyncio
from sqlalchemy import text
from app.db.database import engine

async def migrate():
    async with engine.begin() as conn:
        print("Migrating Admin Dashboard columns...")
        
        # Add admin_chat_id to chats
        try:
            await conn.execute(text("ALTER TABLE chats ADD COLUMN IF NOT EXISTS admin_chat_id BIGINT;"))
            print("Added admin_chat_id to chats")
        except Exception as e:
            print(f"Error adding admin_chat_id: {e}")

        # Add admin_message_id to games
        try:
            await conn.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS admin_message_id BIGINT;"))
            print("Added admin_message_id to games")
        except Exception as e:
            print(f"Error adding admin_message_id: {e}")

    print("Migration finished.")

if __name__ == "__main__":
    asyncio.run(migrate())
