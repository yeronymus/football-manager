
import asyncio
from sqlalchemy import select, delete
from app.db.database import async_session_maker
from app.db.models import Game, GameStats, RatingHistory, User, GameStatus

async def reset_game_2():
    async with async_session_maker() as session:
        print("Starting Reset for Game 2...")
        
        # 1. Fetch Game
        game = await session.get(Game, 2)
        if not game:
            print("Game 2 not found!")
            return

        print(f"Current Status: {game.status}")

        # 2. Revert Ratings
        history_result = await session.execute(select(RatingHistory).where(RatingHistory.game_id == 2))
        histories = history_result.scalars().all()
        
        print(f"Found {len(histories)} rating history entries to revert.")
        
        for h in histories:
            user = await session.get(User, h.user_id)
            if user:
                print(f"Reverting User {user.user_id} ({user.full_name}): Rating {user.rating} -> {h.old_rating}")
                if h.old_rating is not None:
                    user.rating = h.old_rating
                # Decrement games played / stats matches if they were incremented
                user.games_played = max(0, user.games_played - 1)
                user.stats_matches = max(0, user.stats_matches - 1)
        
        # 3. Delete History
        await session.execute(delete(RatingHistory).where(RatingHistory.game_id == 2))
        print("Deleted RatingHistory.")

        # 4. Delete Stats (Goals, MVP)
        stats_result = await session.execute(select(GameStats).where(GameStats.game_id == 2))
        stats = stats_result.scalars().all()
        
        for s in stats:
            if s.is_mvp:
                user = await session.get(User, s.user_id)
                if user:
                    print(f"Reverting MVP count for User {user.user_id}")
                    user.stats_mvp = max(0, user.stats_mvp - 1)
        
        await session.execute(delete(GameStats).where(GameStats.game_id == 2))
        print("Deleted GameStats.")

        # 5. Reset Game
        game.status = GameStatus.ACTIVE
        game.score_a = None
        game.score_b = None
        game.winner_team = None
        
        print("Reset Game status to ACTIVE and cleared scores.")
        
        await session.commit()
        print("Reset Complete!")

if __name__ == "__main__":
    asyncio.run(reset_game_2())
