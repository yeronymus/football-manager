
import asyncio
from sqlalchemy import text
from app.db.database import engine

async def migrate_channel_sync():
    async with engine.begin() as conn:
        print("Migrating: Adding channel columns to games table...")
        try:
            await conn.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS channel_id BIGINT;"))
            await conn.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS channel_message_id BIGINT;"))
            print("Migration successful.")
        except Exception as e:
            print(f"Migration error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_channel_sync())
