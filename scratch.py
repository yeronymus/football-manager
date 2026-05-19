import asyncio
from app.db.database import async_session_maker
from app.db.models import Chat, ChatAdmin
from sqlalchemy import select

async def test():
    async with async_session_maker() as session:
        result = await session.execute(
            select(Chat).join(ChatAdmin).where(ChatAdmin.user_id == 123)
        )
        chats = result.scalars().all()
        print(chats)

asyncio.run(test())
