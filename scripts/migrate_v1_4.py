import asyncio
from sqlalchemy import text
from app.db.database import engine

async def migrate():
    async with engine.connect() as conn:
        print("Adding main_players_count column...")
        try:
            await conn.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS main_players_count INTEGER DEFAULT 22"))
            await conn.commit()
            print("OK.")
        except Exception as e:
            print(f"Error: {e}")

        print("Adding signup_limit column...")
        try:
            await conn.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS signup_limit INTEGER DEFAULT 999"))
            await conn.commit()
            print("OK.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
