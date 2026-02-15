
import asyncio
from sqlalchemy import text
from app.db.database import engine

async def migrate():
    async with engine.begin() as conn:
        print("Migrating Payment Info...")
        
        # Add payment_info column to games table
        # Default value matches the one in models.py
        sql = "ALTER TABLE games ADD COLUMN IF NOT EXISTS payment_info VARCHAR DEFAULT '2924402033/0800';"
        
        try:
            await conn.execute(text(sql))
            print(f"Executed: {sql}")
        except Exception as e:
            print(f"Error executing {sql}: {e}")

    print("Migration finished.")

if __name__ == "__main__":
    asyncio.run(migrate())
