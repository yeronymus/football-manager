from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from app.config import settings

jobstores = {
    'default': RedisJobStore(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        db=0
    )
}

scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="Europe/Prague")

async def start_scheduler(paused: bool = False):
    if scheduler.state == 0:
        scheduler.start(paused=paused)

async def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
