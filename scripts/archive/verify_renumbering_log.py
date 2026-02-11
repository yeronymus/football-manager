import asyncio
import sys
import os
from sqlalchemy import text
sys.path.append(os.getcwd())
from app.db.database import async_session_maker

async def verify():
    async with async_session_maker() as session:
        print("Verifying Game IDs...")
        res_5 = await session.execute(text("SELECT id FROM games WHERE id = 5"))
        if res_5.scalar():
            print("SUCCESS: Game 5 exists.")
        else:
            print("FAILURE: Game 5 NOT found.")

        res_47 = await session.execute(text("SELECT id FROM games WHERE id = 47"))
        if not res_47.scalar():
            print("SUCCESS: Game 47 gone.")
        else:
            print("FAILURE: Game 47 still exists.")

if __name__ == "__main__":
    asyncio.run(verify())
