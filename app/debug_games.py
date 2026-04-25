
import asyncio
from app.db.database import async_session_factory
from app.db.models import Signup, Game, User, Chat, PlayerProfile
from sqlalchemy import select, desc

async def debug_user():
    async with async_session_factory() as session:
        # Get all users to find the one we care about
        users = await session.execute(select(User))
        for u in users.scalars().all():
            print(f"User: {u.user_id} - {u.full_name}")
            
            # Check profiles
            profiles = await session.execute(select(PlayerProfile).where(PlayerProfile.user_id == u.user_id))
            for p in profiles.scalars().all():
                chat = await session.get(Chat, p.chat_id)
                print(f"  Profile in Chat {chat.title if chat else p.chat_id}: {p.games_played} games")
                
                # Check signups
                signups = await session.execute(
                    select(Game)
                    .join(Signup)
                    .where(Signup.user_id == u.user_id, Game.chat_id == p.chat_id)
                )
                sgames = signups.scalars().all()
                print(f"    Signups in DB for this chat: {len(sgames)}")
                for g in sgames:
                    print(f"      Game {g.id}: {g.date_time} (Status: {g.status}, Score: {g.score_a}:{g.score_b})")

if __name__ == "__main__":
    asyncio.run(debug_user())
