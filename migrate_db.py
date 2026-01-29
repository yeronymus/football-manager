
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def migrate_created_at():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()"))
            print("Added created_at to games table.")
        except Exception as e:
            print(f"Error: {e}")
                
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_created_at())
