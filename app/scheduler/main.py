from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings

jobstores = {
    "default": RedisJobStore(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        db=settings.redis_fsm_db,
    )
}

scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    timezone="Europe/Prague",
    job_defaults={
        "misfire_grace_time": 7200,
        "coalesce": True,
    },
)


async def start_scheduler(paused: bool = False):
    if scheduler.state == 0:
        scheduler.start(paused=paused)


async def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
