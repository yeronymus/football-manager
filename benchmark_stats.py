import asyncio
import time
from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import Game, User, Signup, SignupStatus, GameStatus, Team, GameStats
from app.cli.stats import recalculate_stats_command

async def setup_bench_data():
    async with async_session_maker() as s:
        # Create many games and signups
        print("Setting up benchmark data...")
        users = [User(user_id=i, full_name=f"User {i}", player_position="CM") for i in range(1, 101)]
        s.add_all(users)
        await s.commit()

        for i in range(1, 51):
            game = Game(
                chat_id=-1,
                date_time=time.strftime('%Y-%m-%d %H:%M:%S'),
                location="Bench",
                status=GameStatus.FINISHED,
                team_count=2,
                score_a=2,
                score_b=1,
                winner_team=Team.A
            )
            s.add(game)
            await s.flush()
            
            for j in range(1, 11):
                signup = Signup(game_id=game.id, user_id=j, status=SignupStatus.ACTIVE, team=Team.A if j <= 5 else Team.B)
                s.add(signup)
            
            stats = GameStats(game_id=game.id, user_id=1, is_mvp=True)
            s.add(stats)
        
        await s.commit()
        print("Data setup complete.")

async def run_bench():
    start = time.time()
    await recalculate_stats_command(dry_run=True)
    end = time.time()
    print(f"Recalculate stats took: {end - start:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(run_bench())
