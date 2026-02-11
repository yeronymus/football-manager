import asyncio
import sys
import os
from sqlalchemy import text
sys.path.append(os.getcwd())
try:
    from app.db.database import async_session_maker
except ImportError:
    # Fallback if imports fail due to path issues
    sys.path.append(os.path.join(os.getcwd(), 'app'))
    from app.db.database import async_session_maker

async def verify_games():
    async with async_session_maker() as session:
        print("Verifying Game IDs...")
        
        # Check Game 5
        res_5 = await session.execute(text("SELECT id, date_time, status FROM games WHERE id = 5"))
        game_5 = res_5.fetchone()
        if game_5:
            print(f"✅ Game 5 FOUND: {game_5}")
        else:
            print("❌ Game 5 NOT FOUND")

        # Check Game 47
        res_47 = await session.execute(text("SELECT id, date_time, status FROM games WHERE id = 47"))
        game_47 = res_47.fetchone()
        if game_47:
            print(f"❌ Game 47 FOUND: {game_47} (Should be gone!)")
        else:
            print("✅ Game 47 NOT FOUND (Correct)")

        # Check Sequence
        try:
            res_seq = await session.execute(text("SELECT last_value FROM games_id_seq"))
            seq_val = res_seq.scalar()
            print(f"ℹ️ Sequence 'games_id_seq' current value: {seq_val}")
        except Exception as e:
            print(f"⚠️ Could not check sequence: {e}")

if __name__ == "__main__":
    asyncio.run(verify_games())
