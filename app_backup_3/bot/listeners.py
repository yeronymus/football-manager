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
        
        # 1. Format Message
        text = await format_game_message(game, session)
        
        # 2. Update Chat
        if game.chat_id and game.message_id:
            try:
                await _bot.edit_message_text(
                    chat_id=game.chat_id,
                    message_id=game.message_id,
                    text=text,
                    reply_markup=get_game_keyboard(game.id),
                    parse_mode="HTML"
                )
            except Exception as e:
                # Ignore "message is not modified"
                if "message is not modified" not in str(e):
                    logger.warning(f"Failed to update chat message: {e}")

        # 3. Update Channel
        if game.channel_id and game.channel_message_id:
             try:
                await _bot.edit_message_text(
                    chat_id=game.channel_id,
                    message_id=game.channel_message_id,
                    text=text,
                    reply_markup=get_channel_game_keyboard(game.id),
                    parse_mode="HTML"
                )
             except Exception as e:
                if "message is not modified" not in str(e):
                    logger.warning(f"Failed to update channel message: {e}")

        # 4. Update Dashboard
        from app.bot.admin_dashboard import update_dashboard_message
        try:
             await update_dashboard_message(_bot, game.id, session)
        except Exception as e:
             logger.warning(f"Failed to update dashboard: {e}")

