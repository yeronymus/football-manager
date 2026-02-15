import asyncio
import sys
import os
from sqlalchemy import select

# Ensure app is in path
sys.path.append(os.getcwd())
sys.path.append("/app")

async def main():
    from app.db.database import async_session_maker
    from app.db.models import Chat

    async with async_session_maker() as session:
        result = await session.execute(select(Chat))
        chats = result.scalars().all()
        
        print("--- REGISTERED CHATS ---")
        for chat in chats:
            print(f"Chat ID: {chat.chat_id}, Title: {chat.title}, Admin ID: {chat.admin_chat_id}")
        print("--- END CHATS ---")

if __name__ == "__main__":
    asyncio.run(main())
