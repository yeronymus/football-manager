import asyncio
from app.db.database import async_session
from app.db.models import Game, Signup, User
from sqlalchemy import select

async def debug_game():
    async with async_session() as session:
        # Get latest game
        result = await session.execute(select(Game).order_by(Game.id.desc()).limit(1))
        game = result.scalar_one_or_none()
        
        if not game:
            print("No games found")
            return

        print(f"Game ID: {game.id} | Status: {game.status} | Date: {game.date_time}")
        
        # Get Signups
        result = await session.execute(
            select(User, Signup)
            .join(Signup)
            .where(Signup.game_id == game.id)
        )
        data = result.all()
        
        print("\n--- PLAYERS ---")
        for u, s in data:
            print(f"ID: {u.user_id} | Name: {u.full_name} | Team: {s.team} | Status: {s.status}")

if __name__ == "__main__":
    asyncio.run(debug_game())
