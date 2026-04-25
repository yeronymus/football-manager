
import asyncio
from app.db.database import async_session_factory
from app.db.models import Chat, Game, GameStatus
from sqlalchemy import select

async def list_games():
    async with async_session_factory() as session:
        # Find the chat
        chat_res = await session.execute(select(Chat).where(Chat.title.ilike("%Czech Premier League%")))
        chats = chat_res.scalars().all()
        
        if not chats:
            print("Chat 'Czech Premier League' not found.")
            # List all chats to be sure
            all_chats = await session.execute(select(Chat))
            print("Available chats:")
            for c in all_chats.scalars().all():
                print(f" - {c.title} (ID: {c.chat_id})")
            return

        for chat in chats:
            print(f"\nGames for chat: {chat.title} (ID: {chat.chat_id})")
            games_res = await session.execute(
                select(Game).where(Game.chat_id == chat.chat_id).order_by(Game.date_time.desc())
            )
            games = games_res.scalars().all()
            print(f"Found {len(games)} games in this chat.")
            for g in games:
                print(f" - ID: {g.id} | Date: {g.date_time} | Score: {g.score_a}:{g.score_b} | Status: {g.status}")

if __name__ == "__main__":
    asyncio.run(list_games())
