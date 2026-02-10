
import asyncio
import sys
sys.path.append('/app')
from app.db.database import async_session_maker
from app.db.models import Game
from sqlalchemy import select

async def check_game():
    async with async_session_maker() as session:
        game = await session.get(Game, 47)
        if game:
            print(f"--- GAME 47 ---")
            print(f"Max Players: {game.max_players}")
            print(f"GK Hours: {game.gk_hours}")
            print(f"Status: {game.status}")
            print(f"Active GK A: {game.has_active_gk_a}")
            print(f"Active GK B: {game.has_active_gk_b}")
            # Count signups
            from app.db.models import Signup, SignupStatus
            res = await session.execute(
                select(Signup).where(Signup.game_id == 47, Signup.status == SignupStatus.ACTIVE)
            )
            count = len(res.scalars().all())
            print(f"Active Count: {count}")
            
            # Check waiting list
            res_w = await session.execute(
                select(Signup).where(Signup.game_id == 47, Signup.status == SignupStatus.RESERVE)
            )
            w_count = len(res_w.scalars().all())
            print(f"Waiting List: {w_count}")

if __name__ == "__main__":
    asyncio.run(check_game())
