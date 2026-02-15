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

    async with async_session_maker() as session:
        # Get Game 6 to find the correct chat_id
        result = await session.execute(select(Game).where(Game.id == 6))
        game_6 = result.scalar_one_or_none()
        
        if not game_6:
            # Try Game 47 if it exists
            result = await session.execute(select(Game).where(Game.id == 47))
            game_6 = result.scalar_one_or_none()

        if not game_6:
            print("Could not find Game 6 or 47 to get chat_id")
            return

        correct_chat_id = game_6.chat_id
        print(f"Correct Chat ID found: {correct_chat_id}")

        # Update Game 5
        result = await session.execute(select(Game).where(Game.id == 5))
        game_5 = result.scalar_one_or_none()
        
        if game_5:
            print(f"Game 5 current chat_id: {game_5.chat_id}")
            if game_5.chat_id != correct_chat_id:
                game_5.chat_id = correct_chat_id
                print(f"Updated Game 5 chat_id to {correct_chat_id}")
                await session.commit()
                
                # Re-trigger voting automatically
                print("Re-triggering voting message...")
                from app.scheduler.tasks import send_voting_message
                try:
                    await send_voting_message(5)
                    print("Voting message sent successfully to corrected chat!")
                except Exception as ve:
                    print(f"Failed to send voting message: {ve}")
            else:
                print("Game 5 chat_id is already same as Game 6")
        else:
            print("Game 5 not found")

if __name__ == "__main__":
    asyncio.run(main())
