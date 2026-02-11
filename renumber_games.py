import asyncio
import sys
import os
from sqlalchemy import text
sys.path.append(os.getcwd())
from app.db.database import async_session_maker

async def renumber_game():
    async with async_session_maker() as session:
        print("Starting Game ID Correction...")
        
        # 1. Verify Game 47 exists and Game 5 does NOT
        res_47 = await session.execute(text("SELECT id FROM games WHERE id = 47"))
        if not res_47.scalar():
            print("Game 47 not found. Aborting.")
            return

        res_5 = await session.execute(text("SELECT id FROM games WHERE id = 5"))
        if res_5.scalar():
            print("Game 5 ALREADY exists. Cannot overwrite. Aborting.")
            return

        print("Renaming Game 47 -> 5...")
        
        # 2. Update Foreign Keys first
        print("Updating related tables...")
        await session.execute(text("UPDATE signups SET game_id = 5 WHERE game_id = 47"))
        await session.execute(text("UPDATE votes SET game_id = 5 WHERE game_id = 47"))
        await session.execute(text("UPDATE rating_history SET game_id = 5 WHERE game_id = 47"))
        await session.execute(text("UPDATE game_stats SET game_id = 5 WHERE game_id = 47"))
        
        # 3. Update Game itself
        await session.execute(text("UPDATE games SET id = 5 WHERE id = 47"))
        
        # 4. Reset Sequence to 6
        print("Resetting sequence to 6...")
        await session.execute(text("ALTER SEQUENCE games_id_seq RESTART WITH 6"))
        
        await session.commit()
        print("SUCCESS: Game 47 is now Game 5. Next game will be 6.")

if __name__ == "__main__":
    try:
        asyncio.run(renumber_game())
    except Exception as e:
        print(f"Error: {e}")
