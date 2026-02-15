
import asyncio
import sys
# Need to add search path for app module
sys.path.append('/app')

from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import Signup, User, SignupStatus

async def dump_signups():
    try:
        async with async_session_maker() as session:
            # Get all signups for Game 47
            stmt = select(Signup, User).join(User, Signup.user_id == User.user_id).where(Signup.game_id == 47)
            res = await session.execute(stmt)
            signups = res.all()
            
            print(f"--- DUMP Start (Total: {len(signups)}) ---")
            for s, u in signups:
                status_str = str(s.status).replace('SignupStatus.', '')
                print(f"[ID: {u.user_id}] {u.full_name} (@{u.username}) => {status_str}, Pos: {s.position}")
            print("--- DUMP End ---")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(dump_signups())
