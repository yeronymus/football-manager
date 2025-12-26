import logging
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from app.config import settings
from app.bot.middlewares import DbSessionMiddleware, InstanceAccessMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Initialize Bot
bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Initialize Dispatcher
dp = Dispatcher()
dp.message.outer_middleware(InstanceAccessMiddleware())
dp.callback_query.outer_middleware(InstanceAccessMiddleware())

from app.bot.handlers import router as valid_router
from app.bot.game_handlers import router as game_router
from app.bot.admin_handlers import router as admin_router
from app.bot.vote_handlers import router as vote_router
from app.db.database import async_session_maker

dp.include_router(valid_router)
dp.include_router(game_router)
dp.include_router(admin_router)
dp.include_router(vote_router)

dp.update.middleware(DbSessionMiddleware(session_pool=async_session_maker))

async def start_bot():
    """
    Function to start the bot (e.g. set webhook).
    This will be called from the FastAPI startup event.
    This will be called from the FastAPI startup event.
    """
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != settings.WEBHOOK_URL:
        await bot.set_webhook(settings.WEBHOOK_URL)
    
    logging.info(f"Webhook set to {settings.WEBHOOK_URL}")

    # Set Bot Commands
    commands = [
        types.BotCommand(command="start", description="🏠 Главное меню / Регистрация"),
        types.BotCommand(command="my_profile", description="👤 Мой профиль"),
        types.BotCommand(command="my_history", description="📜 Мои игры"),
        types.BotCommand(command="draft", description="⚖️ Драфт (Админ)"),
        types.BotCommand(command="register_chat", description="📢 Подключить чат (Админ)"),
    ]
    await bot.set_my_commands(commands)

    # Set Persistent Menu Button (WebApp)
    web_app_url = f"{settings.WEBAPP_URL}/web/index.html?v=2"
    await bot.set_chat_menu_button(
        menu_button=types.MenuButtonWebApp(
            text="Создать игру", 
            web_app=types.WebAppInfo(url=web_app_url)
        )
    )

async def stop_bot():
    """
    Function to stop the bot (e.g. delete webhook).
    """
    await bot.delete_webhook()
    await bot.session.close()
    logging.info("Bot stopped")

async def main():
    """
    Entry point for polling mode.
    """
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
