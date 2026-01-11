
import asyncio
from sqlalchemy import text
from app.db.database import engine

async def migrate_score():
    async with engine.begin() as conn:
        print("Migrating score_c...")
        try:
            await conn.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS score_c INTEGER DEFAULT NULL;"))
            print("Added score_c column.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_score())
