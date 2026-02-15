
import subprocess

def run():
    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz",
        "docker exec football-prod_app_1 python3 -c \"
import asyncio
from app.scheduler.tasks import publish_game_task
from app.db.database import async_session_maker
from app.db.models import Game
from sqlalchemy import select

async def force():
    async with async_session_maker() as session:
        # Find the game
        res = await session.execute(select(Game).where(Game.id == 47))
        game = res.scalar_one_or_none()
        if not game:
            print('Game 47 not found')
            return
        
        await publish_game_task(47)
        print('DONE')

asyncio.run(force())
\""
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    print("RC:", result.returncode)

if __name__ == "__main__":
    run()
