import asyncio
from sqlalchemy import text
from app.db.database import engine

async def migrate():
    async with engine.begin() as conn:
        print("Adding 'duration' column to 'games' table...")
        try:
            await conn.execute(text("ALTER TABLE games ADD COLUMN duration INTEGER DEFAULT 2"))
            print("Successfully added 'duration' column.")
        except Exception as e:
            if "already exists" in str(e):
                print("Column 'duration' already exists.")
            else:
                print(f"Error adding column: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
