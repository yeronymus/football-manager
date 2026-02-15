import asyncio
from sqlalchemy import text
from app.db.database import engine

async def migrate_stats():
    async with engine.begin() as conn:
        print("Migrating game_stats columns...")
        try:
            # Add goals, assists, is_mvp if they don't exist
            await conn.execute(text("ALTER TABLE game_stats ADD COLUMN IF NOT EXISTS goals INTEGER DEFAULT 0;"))
            await conn.execute(text("ALTER TABLE game_stats ADD COLUMN IF NOT EXISTS assists INTEGER DEFAULT 0;"))
            await conn.execute(text("ALTER TABLE game_stats ADD COLUMN IF NOT EXISTS is_mvp BOOLEAN DEFAULT FALSE;"))
            print("Successfully added missing columns to game_stats.")
        except Exception as e:
            print(f"Error during migration: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_stats())
