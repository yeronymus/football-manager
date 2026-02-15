import asyncio
from app.db.database import get_session
from app.db.models import Game, Vote
from sqlalchemy import select, func
from app.scheduler.tasks import send_voting_message
from datetime import datetime
import time

async def schedule_vote_msg():
    print("Waiting until 15:30 to send voting message...")
    
    while True:
        now = datetime.now()
        # Wait until 15:30
        if (now.hour > 15) or (now.hour == 15 and now.minute >= 30):
            break
        print(f"Current time: {now.strftime('%H:%M:%S')}. Waiting for 15:30... Sleeping 60s...")
        time.sleep(60)

    print("It's 15:30! Checking voting status...")
    async for session in get_session():
        # Find active or just finished game today
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await session.execute(
            select(Game)
            .where(Game.date_time >= today_start)
            .order_by(Game.date_time.desc())
            .limit(1)
        )
        game = result.scalar_one_or_none()
        
        if not game:
            print("No game found today.")
            return

        print(f"Found game: {game.id} at {game.location}")

        # Check for existing votes
        vote_result = await session.execute(
            select(func.count(Vote.id)).where(Vote.game_id == game.id)
        )
        vote_count = vote_result.scalar()

        if vote_count > 0:
            print(f"⚠️ Votes detected ({vote_count}). Voting seems to have already started automatically. Script will NOT send message.")
            return

        print(f"No votes detected. Sending voting message...")
        try:
            await send_voting_message(game.id)
            print("Message sent successfully!")
        except Exception as e:
            print(f"Error sending message: {e}")

if __name__ == "__main__":
    asyncio.run(schedule_vote_msg())
