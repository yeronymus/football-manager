from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from app.config import settings

jobstores = {
    'default': RedisJobStore(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0
    )
}

scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="Europe/Moscow")

async def start_scheduler():
    scheduler.start()

async def stop_scheduler():
    scheduler.shutdown()
