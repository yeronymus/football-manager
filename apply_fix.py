
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found")
        return
    
    # Replace postgresql:// with postgresql+asyncpg:// if needed
    if db_url.startswith("postgresql://") and "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        print(f"Applying migration to {db_url}...")
        await conn.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS registration_hours INTEGER DEFAULT 0;"))
        print("Migration applied!")
        
        res = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='games' AND column_name='registration_hours';"))
        cols = res.fetchall()
        print(f"Columns check: {cols}")

if __name__ == "__main__":
    asyncio.run(main())
