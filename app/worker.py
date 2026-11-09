import asyncio
import logging
import pathlib
import sys
import time
from app.bot.instance import bot
from app.bot.main import start_bot, stop_bot
from app.config import settings
from app.db.database import init_models
from app.infrastructure.messaging import consumer as msg_consumer
from app.scheduler.main import start_scheduler, stop_scheduler

HEARTBEAT_PATH = pathlib.Path("/tmp/worker_heartbeat")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("worker")


def _write_heartbeat() -> None:
    try:
        HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_PATH.write_text(str(time.time()), encoding="utf-8")
    except Exception:
        pass


async def _scheduler_tick(sched):
    """Periodically wakes up scheduler and updates liveness heartbeat."""
    while True:
        try:
            _write_heartbeat()
            await asyncio.sleep(15)
            if sched.running:
                sched.wakeup()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Scheduler tick error: {e}")


async def main():
    logger.info("Starting background worker...")
    _write_heartbeat()

    try:
        await init_models()
    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Starting scheduler...")
    await start_scheduler(paused=False)
    from app.scheduler.main import scheduler
    from app.infrastructure.scheduler.service import SchedulerService
    from app.scheduler.tasks import check_unopened_voting_task

    SchedulerService().schedule_periodic_unopened_voting_check()
    asyncio.create_task(check_unopened_voting_task())

    sched_tick_task = asyncio.create_task(_scheduler_tick(scheduler))

    logger.info("Starting messaging consumer...")
    await msg_consumer.start()

    logger.info("Initializing bot commands and webhook...")
    try:
        await start_bot()
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}", exc_info=True)

    polling_task = None
    if settings.use_polling:
        logger.info("Starting bot in POLLING mode in worker...")
        from app.bot.main import dp

        polling_task = asyncio.create_task(dp.start_polling(bot))

    _write_heartbeat()
    logger.info("Worker is fully started and running.")

    try:
        await asyncio.Event().wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received. Shutting down worker...")
    finally:
        if polling_task and not polling_task.done():
            from app.bot.main import dp

            await dp.stop_polling()
            polling_task.cancel()

        if sched_tick_task and not sched_tick_task.done():
            sched_tick_task.cancel()

        logger.info("Stopping scheduler...")
        await stop_scheduler()

        logger.info("Stopping messaging consumer...")
        await msg_consumer.stop()

        logger.info("Stopping bot connection...")
        await stop_bot()

        logger.info("Worker stopped successfully.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
