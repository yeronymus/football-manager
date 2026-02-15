from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from app.config import settings

jobstores = {
    'default': RedisJobStore(
        host=settings.redis_host,
        port=settings.redis_port,
        db=0
    )
}

scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="Europe/Prague")

async def start_scheduler():
    scheduler.start()

async def stop_scheduler():
    scheduler.shutdown()
