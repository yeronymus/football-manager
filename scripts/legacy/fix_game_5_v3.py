import asyncio
import sys
import os
from sqlalchemy import select

# Ensure app is in path
sys.path.append(os.getcwd())
sys.path.append("/app")

async def main():
    from app.db.database import async_session_maker
    from app.db.models import Game

    # The ID we found in logs that was queried from chats table
    GROUP_CHAT_ID = -1003437568976
    # The current ID in Game 5 which user says is the channel
    CHANNEL_ID = -1003625911268

    async with async_session_maker() as session:
        result = await session.execute(select(Game).where(Game.id == 5))
        game = result.scalar_one_or_none()
        
        if not game:
            print("Game 5 not found")
            return

        print(f"Current Game 5: chat_id={game.chat_id}, channel_id={game.channel_id}")
        
        if game.chat_id != GROUP_CHAT_ID:
            print(f"Updating chat_id to {GROUP_CHAT_ID}")
            game.chat_id = GROUP_CHAT_ID
            game.channel_id = CHANNEL_ID
            await session.commit()
            print("Update committed.")
        else:
            print("chat_id already matches GROUP_CHAT_ID.")

        # Trigger voting message to the NEW chat_id
        from app.scheduler.tasks import send_voting_message
        try:
            print("Re-triggering voting message...")
            await send_voting_message(5)
            print("Voting sent successfully to GROUP chat!")
        except Exception as e:
            print(f"Failed to send voting: {e}")

if __name__ == "__main__":
    asyncio.run(main())
