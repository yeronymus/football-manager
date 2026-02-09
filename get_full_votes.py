import asyncio
from sqlalchemy import select, func
from app.db.database import async_session_maker
from app.db.models import Vote, User, Team

async def get_full_results():
    async with async_session_maker() as session:
        for team in [Team.A, Team.B]:
            print(f"\n--- TEAM {team.value} ---")
            result = await session.execute(
                select(User.full_name, func.count(Vote.id))
                .join(Vote, User.user_id == Vote.target_id)
                .where(Vote.game_id == 2, Vote.vote_team == team)
                .group_by(User.full_name)
                .order_by(func.count(Vote.id).desc())
            )
            for name, count in result.all():
                print(f"{name}: {count} голосов")

if __name__ == "__main__":
    asyncio.run(get_full_results())
