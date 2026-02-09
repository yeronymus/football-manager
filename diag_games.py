import asyncio
from app.db.database import async_session_maker
from app.db.models import Game, Signup, User, GameStats, RatingHistory
from sqlalchemy import select, func

async def check_game_2():
    async with async_session_maker() as session:
        # 1. Game Status
        result = await session.execute(select(Game).where(Game.id == 2))
        game = result.scalar_one_or_none()
        if game:
            print(f"GAME 2: Status={game.status}, ScoreA={game.score_a}, ScoreB={game.score_b}, Winner={game.winner_team}")
        else:
            print("GAME 2 NOT FOUND")

        # 2. GameStats
        result = await session.execute(select(func.count(GameStats.id)).where(GameStats.game_id == 2))
        stats_count = result.scalar()
        print(f"GAME 2 STATS COUNT: {stats_count}")

        # 3. RatingHistory
        result = await session.execute(select(func.count(RatingHistory.id)).where(RatingHistory.game_id == 2))
        history_count = result.scalar()
        print(f"GAME 2 RATING HISTORY COUNT: {history_count}")

        # 4. Signups
        result = await session.execute(select(func.count(Signup.id)).where(Signup.game_id == 2))
        signup_count = result.scalar()
        print(f"GAME 2 SIGNUP COUNT: {signup_count}")

if __name__ == "__main__":
    asyncio.run(check_game_2())
