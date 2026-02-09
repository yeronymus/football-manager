import asyncio
from sqlalchemy import text
from app.db.database import get_session

async def fix_schema():
    print("Fixing database schema...")
    async for session in get_session():
        try:
            # Add channel_id
            await session.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS channel_id BIGINT;"))
            # Add channel_message_id
            await session.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS channel_message_id INTEGER;"))
            # Add admin_message_id
            await session.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS admin_message_id INTEGER;"))
            
            await session.commit()
            print("Schema updated successfully!")
        except Exception as e:
            print(f"Error updating schema: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(fix_schema())
