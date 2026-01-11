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

from app.bot.admin_tools import router as tools_router
dp.include_router(tools_router)

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

    # Set Bot Commands ...
    logging.info("Setting bot commands...")
    
    # 1. Clear existing commands to force update
    try:
        await bot.delete_my_commands(scope=types.BotCommandScopeDefault())
        await bot.delete_my_commands(scope=types.BotCommandScopeAllPrivateChats())
        logging.info("Cleared default and private commands.")
    except Exception as e:
        logging.warning(f"Failed to clear commands: {e}")

    # 2. Set new commands
    # Common commands for everyone
    user_commands = [
        types.BotCommand(command="start", description="🏠 Меню"),
        types.BotCommand(command="create", description="➕ Создать"),
        types.BotCommand(command="my_profile", description="👤 Профиль"),
        types.BotCommand(command="my_history", description="📜 История"),
    ]
    
    # Admin-only commands (appended to user commands)
    admin_commands = user_commands + [
        types.BotCommand(command="draft", description="⚖️ Драфт / Составы"),
        types.BotCommand(command="finish", description="🏁 Завершить матч"),
        types.BotCommand(command="register_chat", description="📢 Подключить чат"),
        types.BotCommand(command="setup", description="🕹 God Mode"),
    ]

    # Set Default Scope (For groups etc)
    await bot.set_my_commands(user_commands, scope=types.BotCommandScopeDefault())
    
    # Set Private Chats Scope (Explicitly for all private chats)
    await bot.set_my_commands(user_commands, scope=types.BotCommandScopeAllPrivateChats())
    
    # Set Admin Scope (For specific admins in private chat)
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.set_my_commands(admin_commands, scope=types.BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logging.warning(f"Failed to set commands for admin {admin_id}: {e}")

    logging.info("Set role-based commands successfully.")
    
    # 3. Force 'Commands' menu button explicitly
    logging.info("Setting menu button to COMMANDS...")
    await bot.set_chat_menu_button(menu_button=types.MenuButtonCommands())

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
