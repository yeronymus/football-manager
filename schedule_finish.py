import asyncio
import os
import sys
from datetime import datetime, timedelta
from app.scheduler.main import scheduler
from app.scheduler.tasks import calculate_mvp
from app.db.database import async_session_maker

GAME_ID = 2
HOURS = 5

async def schedule_finish():
    print(f"SCHEDULING MVP Calculation for Game {GAME_ID} in {HOURS} hours...")
    
    # We need to initialize the scheduler (connect to Redis)
    # But scheduler is already initialized in main.py?
    # We need to start it locally to add the job?
    # Or just add to the store.
    # APScheduler needs start() to process, but add_job works if store is configured.
    # However, since we are running as a separate script, we need to ensure we connect to the SAME Redis.
    # settings.redis_host is 'redis' inside docker.
    # If running inside docker exec, 'redis' resolves.
    
    run_date = datetime.now() + timedelta(hours=HOURS)
    
    try:
        scheduler.add_job(
            calculate_mvp, 
            'date', 
            run_date=run_date, 
            args=[GAME_ID],
            id=f"calculate_mvp_{GAME_ID}",
            replace_existing=True
        )
        print(f"✅ Job scheduled for {run_date} (ID: calculate_mvp_{GAME_ID})")
    except Exception as e:
        print(f"❌ Failed to schedule: {e}")

if __name__ == "__main__":
    # We need to ensure settings load correctly for Redis connection
    # Config is loaded at module level.
    # But we might need to await something? No, add_job is sync/async safe usually?
    # Wait, Reference: scheduler.add_job returns Job.
    # Just running this script add the job to Redis.
    # The MAIN process (bot) will pick it up because it polls Redis.
    schedule_finish() # It's sync wrapper? No, async def.
    asyncio.run(schedule_finish())
