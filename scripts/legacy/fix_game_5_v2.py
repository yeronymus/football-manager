import asyncio
import sys
import os
from sqlalchemy import select

# Ensure app is in path
sys.path.append(os.getcwd())
sys.path.append("/app")

async def main():
    from app.db.database import async_session_maker
    from app.db.models import Game, Chat

    async with async_session_maker() as session:
        # 1. Get Game 5
        result = await session.execute(select(Game).where(Game.id == 5))
        game = result.scalar_one_or_none()
        if not game:
            print("Game 5 not found")
            return
        
        current_chat_id = game.chat_id
        print(f"Current Game 5 Chat ID: {current_chat_id}")

        # 2. Get all chats
        result = await session.execute(select(Chat))
        chats = result.scalars().all()
        
        print(f"Found {len(chats)} registered chats.")
        
        # 3. Heuristic: Find the group and channel
        # If we have only 1 chat that is NOT current_chat_id, it might be the group.
        # Or if one chat title contains 'Channel' vs 'Group'.
        # For now, let's just print them all carefully.
        
        potential_group = None
        for chat in chats:
            print(f"Chat: {chat.chat_id} | Title: {chat.title}")
            if chat.chat_id != current_chat_id:
                potential_group = chat.chat_id
        
        if potential_group:
            print(f"Proposed Update: chat_id={potential_group}, channel_id={current_chat_id}")
            # Do the update
            game.chat_id = potential_group
            game.channel_id = current_chat_id
            await session.commit()
            print("Successfully updated Game 5 IDs.")
            
            # Notify admin directly
            from app.config import settings
            from app.bot.main import bot
            msg = f"🔍 <b>VOTING FIX</b>\nGame 5 updated from {current_chat_id} to {potential_group}.\n\n<b>Chats found:</b>\n"
            msg += "\n".join([f"{c.chat_id}: {c.title}" for c in chats])
            for admin_id in settings.admin_ids:
                try: await bot.send_message(admin_id, msg, parse_mode="HTML")
                except: pass

        else:
            print("No potential group found in chats table.")

if __name__ == "__main__":
    asyncio.run(main())
