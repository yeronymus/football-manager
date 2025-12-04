import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Initialize Bot
bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Initialize Dispatcher
dp = Dispatcher()

from app.bot.handlers import router as registration_router
from app.bot.game_handlers import router as game_router
from app.bot.vote_handlers import router as vote_router
from app.bot.middlewares import DbSessionMiddleware
from app.db.database import async_session_maker

dp.include_router(registration_router)
dp.include_router(game_router)
dp.include_router(vote_router)

dp.update.middleware(DbSessionMiddleware(session_pool=async_session_maker))

async def start_bot():
    """
    Function to start the bot (e.g. set webhook).
    This will be called from the FastAPI startup event.
    """
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != settings.WEBHOOK_URL:
        await bot.set_webhook(settings.WEBHOOK_URL)
    
    logging.info(f"Webhook set to {settings.WEBHOOK_URL}")

async def stop_bot():
    """
    Function to stop the bot (e.g. delete webhook).
    """
    await bot.delete_webhook()
    await bot.session.close()
    logging.info("Bot stopped")
