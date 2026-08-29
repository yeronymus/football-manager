import asyncio
import logging
import sys
from app.config import settings
from app.db.database import init_models
from app.scheduler.main import start_scheduler, stop_scheduler
from app.infrastructure.messaging import consumer as msg_consumer
from app.bot.instance import bot
from app.bot.main import start_bot, stop_bot

# Setup logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("worker")

async def main():
    logger.info("Starting background worker...")
    
    # 1. Run migrations
    try:
        await init_models()
    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}", exc_info=True)
        sys.exit(1)
        
    # 2. Start scheduler
    logger.info("Starting scheduler...")
    await start_scheduler()
    
    # 3. Start messaging consumer
    logger.info("Starting messaging consumer...")
    await msg_consumer.start()
    
    # 4. Initialize bot webhook and commands
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

    logger.info("Worker is fully started and running.")
    
    # Keep the worker running until interrupted
    try:
        # Await on an event that never fires to keep the loop alive
        await asyncio.Event().wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received. Shutting down worker...")
    finally:
        # Cleanup
        if polling_task and not polling_task.done():
            from app.bot.main import dp
            await dp.stop_polling()
            polling_task.cancel()

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
