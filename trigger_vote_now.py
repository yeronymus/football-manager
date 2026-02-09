import asyncio
from sqlalchemy import select
from app.db.database import get_session
from app.db.models import Game
from app.scheduler.tasks import send_voting_message

async def trigger_vote():
    async for session in get_session():
        # Find latest game
        result = await session.execute(
            select(Game)
            .order_by(Game.date_time.desc())
            .limit(1)
        )
        game = result.scalar_one_or_none()
        
        if not game:
            print("No games found.")
            return

        print(f"Triggering vote for Game {game.id}...")
        try:
            from app.bot.main import bot # Local import to avoid circular dep if any
            await send_voting_message(game.id)
            print("Voting message sent!")
        except Exception as e:
            print(f"Error sending vote: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(trigger_vote())
