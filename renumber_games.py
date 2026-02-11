import asyncio
import sys
import os
from sqlalchemy import text
sys.path.append(os.getcwd())
from app.db.database import async_session_maker

async def renumber_game():
    async with async_session_maker() as session:
        print("Starting Game ID Correction...")
        
        try:
            # 1. Verify Game 47 exists and Game 5 does NOT
            res_47 = await session.execute(text("SELECT id FROM games WHERE id = 47"))
            if not res_47.scalar():
                print("Game 47 not found. Aborting.")
                return

            res_5 = await session.execute(text("SELECT id FROM games WHERE id = 5"))
            if res_5.scalar():
                print("Game 5 ALREADY exists. Cannot overwrite. Aborting.")
                return

            print("Renaming Game 47 -> 5 (via Copy-Update)...")
            
            # 2. INSERT New Game (ID=5) as copy of 47
            # We explicitly select all columns to preserve data exactly
            cols = [
                "chat_id", "created_by", "date_time", "location", "max_players", "price", "payment_info", 
                "team_count", "gk_hours", "duration", "status", "winner_team", "score_a", "score_b", "score_c", 
                "message_id", "channel_id", "channel_message_id", "admin_message_id", 
                "has_active_gk_a", "has_active_gk_b", "has_active_gk_c", "created_at"
            ]
            cols_str = ", ".join(cols)
            
            print("Creating Game 5 (Clone)...")
            await session.execute(text(f"""
                INSERT INTO games (id, {cols_str})
                SELECT 5, {cols_str}
                FROM games WHERE id = 47
            """))
            
            # 3. Update Foreign Keys to point to 5
            print("Repointing related tables...")
            await session.execute(text("UPDATE signups SET game_id = 5 WHERE game_id = 47"))
            await session.execute(text("UPDATE votes SET game_id = 5 WHERE game_id = 47"))
            await session.execute(text("UPDATE rating_history SET game_id = 5 WHERE game_id = 47"))
            await session.execute(text("UPDATE game_stats SET game_id = 5 WHERE game_id = 47"))
            
            # 4. Delete Old Game
            print("Deleting Game 47...")
            await session.execute(text("DELETE FROM games WHERE id = 47"))
            
            # 5. Reset Sequence to 6
            print("Resetting sequence to 6...")
            await session.execute(text("ALTER SEQUENCE games_id_seq RESTART WITH 6"))
            
            await session.commit()
            print("SUCCESS: Game 47 is now Game 5. Next game will be 6.")
            
        except Exception as e:
            await session.rollback()
            print(f"FAILED: {e}")
            raise e

if __name__ == "__main__":
    try:
        asyncio.run(renumber_game())
    except Exception as e:
        print(f"Error: {e}")
