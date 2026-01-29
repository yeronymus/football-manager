
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

SIMPLE_DB_URL = settings.DATABASE_URL.replace("+asyncpg", "")

async def migrate_enum():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        # Postgres doesn't support "ALTER TYPE ... ADD VALUE IF NOT EXISTS" easily in one block transaction sometimes.
        # But asyncpg usually handles it.
        # We need to run these one by one.
        
        new_values = [
            "LB", "CB", "RB", "LWB", "RWB",
            "CDM", "CM", "CAM", "LM", "RM",
            "LW", "RW", "SS", "ST"
        ]
        
        for val in new_values:
            try:
                await conn.execute(text(f"ALTER TYPE position ADD VALUE IF NOT EXISTS '{val}'"))
                print(f"Added {val}")
            except Exception as e:
                print(f"Error adding {val} (maybe exists): {e}")
                
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_enum())
