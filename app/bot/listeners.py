import logging
from aiogram import Bot
from app.core.events import event_bus
from app.core.services.roster import PlayerJoinedEvent, PlayerLeftEvent
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard, get_channel_game_keyboard
from app.db.database import async_session_maker
from app.db.models import Game

logger = logging.getLogger(__name__)

_bot: Bot | None = None

def setup_listeners(bot: Bot):
    global _bot
    _bot = bot
    event_bus.subscribe(PlayerJoinedEvent, on_player_joined)
    event_bus.subscribe(PlayerLeftEvent, on_player_left)
    logger.info("Event listeners registered.")

async def on_player_joined(event: PlayerJoinedEvent):
    await update_game_ui(event.game_id)

async def on_player_left(event: PlayerLeftEvent):
    if event.promoted_user and _bot:
        try:
            await _bot.send_message(
                event.promoted_user.user_id,
                f"🎉 <b>Вас перевели в основной состав!</b>\nКто-то выписался из игры.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Failed to notify promoted user: {e}")
            
    await update_game_ui(event.game_id)

async def update_game_ui(game_id: int):
    if not _bot: return
    
    async with async_session_maker() as session:
        game = await session.get(Game, game_id)
        if not game: return
        
        # 1. Update Game Messages (Chat & Channel)
        from app.bot.utils import update_game_message
        try:
            await update_game_message(_bot, game, session)
        except Exception as e:
            logger.warning(f"Failed to update game messages: {e}")

        # 4. Update Dashboard
        from app.bot.admin_dashboard import update_dashboard_message
        try:
             await update_dashboard_message(_bot, game.id, session)
        except Exception as e:
             logger.warning(f"Failed to update dashboard: {e}")

