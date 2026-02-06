import asyncio
import sys
import os
from sqlalchemy import select, func, desc
from app.db.database import async_session_maker
from app.db.models import User, GameStats, Game, GameStatus

# Setup Path
sys.path.insert(0, os.getcwd())

async def get_top_stats():
    async with async_session_maker() as session:
        # 1. Top 10 by Rating
        res_rating = await session.execute(
            select(User)
            .where(User.games_played > 0)
            .order_by(desc(User.rating), desc(User.games_played))
            .limit(10)
        )
        top_rating = res_rating.scalars().all()

        # 2. Top Goals (Everyone with 2+ goals)
        res_goals = await session.execute(
            select(User.full_name, func.sum(GameStats.goals).label("total_goals"))
            .join(GameStats, User.user_id == GameStats.user_id)
            .group_by(User.user_id, User.full_name)
            .having(func.sum(GameStats.goals) >= 2)
            .order_by(desc("total_goals"))
        )
        top_goals = res_goals.all()

        # 3. Top MVP
        res_mvp = await session.execute(
            select(User.full_name, User.stats_mvp)
            .where(User.stats_mvp > 0)
            .order_by(desc(User.stats_mvp))
            .limit(5)
        )
        top_mvp = res_mvp.all()

        print("🏆 TOP 10 ПО РЕЙТИНГУ:")
        for i, u in enumerate(top_rating, 1):
             print(f"{i}. {u.full_name} — {u.rating} MMR ({u.games_played} игр)")

        print("\n⚽ СПИСОК БОМБАРДИРОВ (2+ гола):")
        for i, row in enumerate(top_goals, 1):
            print(f"{i}. {row[0]} — {row[1]} гол(ов)")
            
        print("\n🌟 ЗАЧЕТ MVP (Top 5):")
        for i, row in enumerate(top_mvp, 1):
            print(f"{i}. {row[0]} — {row[1]} ⭐️")

if __name__ == "__main__":
    asyncio.run(get_top_stats())
