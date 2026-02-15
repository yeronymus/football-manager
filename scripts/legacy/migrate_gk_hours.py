
import asyncio
from sqlalchemy import text
from app.db.database import engine

async def migrate_gk_hours():
    async with engine.begin() as conn:
        print("Migrating gk_hours...")
        try:
            await conn.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS gk_hours INTEGER DEFAULT 48;"))
            print("Added gk_hours column.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_gk_hours())
