import logging
import sys
from sqlalchemy import select
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from app.config import settings
from app.bot.middlewares import DbSessionMiddleware, InstanceAccessMiddleware, TenantMiddleware

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

from aiogram.fsm.storage.redis import RedisStorage
from app.bot.listeners import setup_listeners


from app.bot.instance import bot

# Initialize Storage (Redis)
storage = RedisStorage.from_url(settings.REDIS_URL)

# Initialize Dispatcher
dp = Dispatcher(storage=storage)
dp.message.outer_middleware(InstanceAccessMiddleware())
dp.callback_query.outer_middleware(InstanceAccessMiddleware())

from app.bot.handlers import router as main_router
from app.db.database import async_session_maker

dp.include_router(main_router)



from app.bot.i18n import SimpleI18n, I18nMiddleware

i18n_instance = SimpleI18n("app/bot/locales")

dp.update.middleware(DbSessionMiddleware(session_pool=async_session_maker))
dp.update.middleware(TenantMiddleware())
dp.update.middleware(I18nMiddleware(i18n=i18n_instance))
dp.update.middleware(InstanceAccessMiddleware())

async def start_bot():
    """
    Function to start the bot. Called from FastAPI startup event.
    """
    try:
        me = await bot.get_me()
        settings.bot_username = me.username
        logging.info(f"Dynamically retrieved bot username: {settings.bot_username}")
    except Exception as e:
        logging.warning(f"Failed to dynamically retrieve bot username, using default: {settings.bot_username}. Error: {e}")

    setup_listeners()

    if settings.webhook_url and not settings.use_polling:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url != settings.webhook_url:
            await bot.set_webhook(settings.webhook_url)

    logging.info(f"Webhook set to {settings.webhook_url}")


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
        types.BotCommand(command="my_profile", description="👤 Профиль"),
        types.BotCommand(command="my_history", description="📜 История"),
        types.BotCommand(command="top", description="🏆 Топ"),
    ]
    
    # Admin-only commands (appended to user commands)
    # Admin-only commands (appended to user commands)
    # We remove context-specifc commands (draft, finish) from the main menu to reduce clutter.
    # They are still available via typing but won't show in the simple menu.
    admin_commands = user_commands + [
        types.BotCommand(command="create", description="➕ Создать игру"),
        types.BotCommand(command="dashboard", description="🛠 Dashboard"),
    ]

    # Set Private Chats Scope (Explicitly for all private chats)
    await bot.set_my_commands(user_commands, scope=types.BotCommandScopeAllPrivateChats())
    
    # Set Group Chats Scope (Empty to hide menu in groups)
    await bot.set_my_commands([], scope=types.BotCommandScopeAllGroupChats())
    
    # Set Default Scope (Empty as fallback)
    await bot.set_my_commands([], scope=types.BotCommandScopeDefault())
    
    # Set Admin Scope (For specific admins in private chat)
    for admin_id in settings.admin_ids:
        try:
            await bot.set_my_commands(admin_commands, scope=types.BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logging.warning(f"Failed to set commands for admin {admin_id}: {e}")

    logging.info("Set role-based commands successfully.")
    
    # 3. Force 'Commands' menu button explicitly (Only for private chats?)
    # Actually, setting commands usually sets the button.
    # To be safe, we might not need set_chat_menu_button if we want it hidden in groups.
    # But let's leave it, as scope modification above is the primary way.
    # await bot.set_chat_menu_button(menu_button=types.MenuButtonCommands()) 

async def stop_bot():
    """
    Function to stop the bot (e.g. delete webhook).
    """
    await bot.delete_webhook()
    await dp.storage.close()
    await bot.session.close()
    logging.info("Bot stopped")

async def main():
    """
    Entry point for polling mode.
    """
    await bot.delete_webhook(drop_pending_updates=True)
    # Ensure commands are set even in polling mode
    await start_bot() 
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
