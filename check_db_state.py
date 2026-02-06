
import asyncio
from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import Game, Signup, User

async def check():
    async with async_session_maker() as session:
        # Get latest game (or ID 1)
        result = await session.execute(select(Game).order_by(Game.id.desc()).limit(1))
        game = result.scalar_one_or_none()
        
        if not game:
            print("No games found.")
            return

        print(f"Game ID: {game.id}")
        print(f"Status: {game.status}")
        print(f"Team Count: {game.team_count}")
        print(f"Message ID: {game.message_id}")
        
        # Signups
        result = await session.execute(select(Signup, User).join(User).where(Signup.game_id == game.id))
        signups = result.all()
        
        print(f"Total Signups: {len(signups)}")
        for s, u in signups:
            print(f"- {u.full_name} ({u.player_position}) | SigPos: {s.position} | Team: {s.team} | Status: {s.status}")

if __name__ == "__main__":
    asyncio.run(check())
