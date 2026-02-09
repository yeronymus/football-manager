import asyncio
from app.db.database import engine
from sqlalchemy import text

async def migrate():
    async with engine.begin() as conn:
        print("Dropping votes table...")
        await conn.execute(text("DROP TABLE IF EXISTS votes CASCADE"))
        print("Done. Table will be recreated on app restart.")

if __name__ == "__main__":
    asyncio.run(migrate())
