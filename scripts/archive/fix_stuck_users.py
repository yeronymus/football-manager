
import asyncio
import sys
sys.path.append('/app')
from app.db.database import async_session_maker
from app.db.models import Signup
from sqlalchemy import delete, select

USER_IDS = [1727698240, 928516797]
GAME_ID = 47

async def fix_stuck():
    async with async_session_maker() as session:
        print(f"Checking stuck signups for Game {GAME_ID}...")
        
        # Select first to see what's there
        stmt = select(Signup).where(Signup.game_id == GAME_ID, Signup.user_id.in_(USER_IDS))
        res = await session.execute(stmt)
        signups = res.scalars().all()
        
        if not signups:
            print("No signups found for these users in Game 47.")
        else:
            for s in signups:
                print(f"Found Signup: User {s.user_id}, Status {s.status}, Pos {s.position}")
            
            # Delete them to allow re-join
            print("Deleting stuck signups...")
            del_stmt = delete(Signup).where(Signup.game_id == GAME_ID, Signup.user_id.in_(USER_IDS))
            await session.execute(del_stmt)
            await session.commit()
            print("Deleted. Users should be able to join now.")

if __name__ == "__main__":
    asyncio.run(fix_stuck())
