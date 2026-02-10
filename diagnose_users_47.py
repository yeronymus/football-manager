
import asyncio
import sys
sys.path.append('/app')
from app.db.database import async_session_maker
from app.db.models import Signup, User, Game
from sqlalchemy import select

USER_IDS = [1727698240, 928516797]
GAME_ID = 47

async def diagnose():
    async with async_session_maker() as session:
        print(f"--- Diagnosing Game {GAME_ID} for {USER_IDS} ---")
        game = await session.get(Game, GAME_ID)
        print(f"Game Status: {game.status}, Max: {game.max_players}")
        
        for uid in USER_IDS:
            # Check Signup
            res = await session.execute(select(Signup).where(Signup.game_id == GAME_ID, Signup.user_id == uid))
            signup = res.scalar_one_or_none()
            
            # Check User name
            u = await session.get(User, uid)
            name = u.full_name if u else "Unknown"
            
            if signup:
                print(f"User {uid} ({name}): Found Signup! Status={signup.status}, Pos={signup.position}")
            else:
                print(f"User {uid} ({name}): No Signup found in DB.")

if __name__ == "__main__":
    asyncio.run(diagnose())
