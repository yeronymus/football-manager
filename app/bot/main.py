import logging
import sys
from aiogram import Dispatcher, types
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
storage = RedisStorage.from_url(
    settings.REDIS_URL,
    connection_kwargs={"health_check_interval": 30, "retry_on_timeout": True}
)

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

# Register tenant and i18n middlewares on message and callback query handlers
dp.message.outer_middleware(TenantMiddleware())
dp.message.outer_middleware(I18nMiddleware(i18n=i18n_instance))

dp.callback_query.outer_middleware(TenantMiddleware())
dp.callback_query.outer_middleware(I18nMiddleware(i18n=i18n_instance))

# Register event bus listeners unconditionally
setup_listeners()

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


    if settings.webhook_url and not settings.use_polling:
        await bot.set_webhook(settings.webhook_url, secret_token=settings.webhook_secret_token)


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
    # English commands (Default)
    user_commands_en = [
        types.BotCommand(command="start", description="🏠 Main Menu"),
        types.BotCommand(command="my_profile", description="👤 Profile"),
        types.BotCommand(command="my_history", description="📜 Match History"),
        types.BotCommand(command="top", description="🏆 Leaderboard"),
        types.BotCommand(command="language", description="🌐 Language / Язык"),
        types.BotCommand(command="rules", description="📋 Rules & Info"),
    ]

    # Russian commands
    user_commands_ru = [
        types.BotCommand(command="start", description="🏠 Главное меню"),
        types.BotCommand(command="my_profile", description="👤 Мой профиль"),
        types.BotCommand(command="my_history", description="📜 История игр"),
        types.BotCommand(command="top", description="🏆 Таблица лидеров"),
        types.BotCommand(command="language", description="🌐 Язык / Language"),
        types.BotCommand(command="rules", description="📋 Правила и инфо"),
    ]
    
    # Admin-only commands (appended to user commands)
    admin_commands_en = user_commands_en + [
        types.BotCommand(command="create", description="➕ Create Match"),
        types.BotCommand(command="dashboard", description="🛠 Dashboard"),
    ]
    admin_commands_ru = user_commands_ru + [
        types.BotCommand(command="create", description="➕ Создать игру"),
        types.BotCommand(command="dashboard", description="🛠 Панель управления"),
    ]

    # Group commands
    group_commands_en = [
        types.BotCommand(command="rules", description="📋 How to Play & Rules"),
        types.BotCommand(command="info", description="ℹ️ Game Info"),
    ]
    group_commands_ru = [
        types.BotCommand(command="rules", description="📋 Как играть и правила"),
        types.BotCommand(command="info", description="ℹ️ Информация об играх"),
    ]

    # Set Private Chats Scope (Default / English)
    await bot.set_my_commands(user_commands_en, scope=types.BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(user_commands_ru, scope=types.BotCommandScopeAllPrivateChats(), language_code="ru")
    
    # Set Group Chats Scope
    await bot.set_my_commands(group_commands_en, scope=types.BotCommandScopeAllGroupChats())
    await bot.set_my_commands(group_commands_ru, scope=types.BotCommandScopeAllGroupChats(), language_code="ru")
    
    # Set Default Scope (Fallback)
    await bot.set_my_commands(user_commands_en, scope=types.BotCommandScopeDefault())
    await bot.set_my_commands(user_commands_ru, scope=types.BotCommandScopeDefault(), language_code="ru")
    
    # Set Admin Scope (For specific admins in private chat)
    import asyncio
    
    async def set_admin_cmds(admin_id):
        try:
            await bot.set_my_commands(admin_commands_en, scope=types.BotCommandScopeChat(chat_id=admin_id))
            await bot.set_my_commands(admin_commands_ru, scope=types.BotCommandScopeChat(chat_id=admin_id), language_code="ru")
        except Exception as e:
            logging.warning(f"Failed to set commands for admin {admin_id}: {e}")

    await asyncio.gather(*(set_admin_cmds(aid) for aid in settings.admin_ids))


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
