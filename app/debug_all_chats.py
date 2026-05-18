
import asyncio
from app.db.database import async_session_maker as async_session_factory
from app.db.models import RatingHistory, Game, Chat, User, PlayerProfile
from sqlalchemy import select
from sqlalchemy.orm import joinedload

async def check_all_games():
    async with async_session_factory() as session:
        # 1. Find the user (assuming we care about the one with the most games if multiple)
        # Actually, let's just find the user with 8 games in any profile
        profiles = await session.execute(
            select(PlayerProfile)
            .options(joinedload(PlayerProfile.user), joinedload(PlayerProfile.chat))
            .where(PlayerProfile.games_played >= 1)
        )
        for p in profiles.scalars().all():
            user = p.user
            chat = p.chat
            print(f"User {user.full_name} ({user.user_id}) in Chat '{chat.title if chat else 'Unknown'}' ({p.chat_id}): {p.games_played} games in Profile")
            
            # Now find all RatingHistory entries for this user/chat combination
            history = await session.execute(
                select(RatingHistory, Game.chat_id)
                .join(Game, Game.id == RatingHistory.game_id)
                .where(RatingHistory.user_id == p.user_id, Game.chat_id == p.chat_id)
            )
            h_list = history.all()
            print(f"  -> Found {len(h_list)} RatingHistory entries for this exact chat_id")
            
            # Check for games for this user in OTHER chats too
            all_history = await session.execute(
                select(RatingHistory, Game.chat_id, Chat.title)
                .join(Game, Game.id == RatingHistory.game_id)
                .outerjoin(Chat, Chat.chat_id == Game.chat_id)
                .where(RatingHistory.user_id == p.user_id)
            )
            ah_list = all_history.all()
            if len(ah_list) != len(h_list):
                print(f"  -> TOTAL across ALL chats: {len(ah_list)}")
                for h, cid, title in ah_list:
                    print(f"     - Game {h.game_id} in Chat '{title}' ({cid})")

if __name__ == "__main__":
    asyncio.run(check_all_games())
