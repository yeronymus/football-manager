"""
listeners.py — Bot-side event handlers.

Subscribes to domain events from core/events.py and reacts by updating
the Telegram UI. This module knows about the bot, but core/ does NOT.

The bot object is imported from instance.py (no circular deps).
The _bot global and setup_listeners(bot) pattern are intentionally removed.
"""
import logging
from app.core.events import event_bus, GameStateChangedEvent, GameMessageNeedsUpdateEvent
from app.core.services.roster import PlayerJoinedEvent, PlayerLeftEvent
from app.bot.instance import bot
from app.db.database import async_session_maker
from app.db.models import Game

logger = logging.getLogger(__name__)


def setup_listeners():
    """Register all bot-side event handlers. Call once at startup."""
    event_bus.subscribe(GameStateChangedEvent, on_game_state_changed)
    event_bus.subscribe(GameMessageNeedsUpdateEvent, on_game_message_needs_update)
    event_bus.subscribe(PlayerJoinedEvent, on_player_joined)
    event_bus.subscribe(PlayerLeftEvent, on_player_left)
    logger.info("Event listeners registered.")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def on_game_state_changed(event: GameStateChangedEvent):
    """Full UI refresh: dashboard + public message."""
    await _refresh_full(event.game_id)


async def on_game_message_needs_update(event: GameMessageNeedsUpdateEvent):
    """Only refresh the public group/channel message."""
    await _refresh_public_message(event.game_id)


async def on_player_joined(event: PlayerJoinedEvent):
    await _refresh_full(event.game_id)


async def on_player_left(event: PlayerLeftEvent):
    if event.promoted_user:
        try:
            await bot.send_message(
                event.promoted_user.user_id,
                "🎉 <b>Вас перевели в основной состав!</b>\nКто-то выписался из игры.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Failed to notify promoted user: {e}")
    await _refresh_full(event.game_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _refresh_full(game_id: int):
    """Refresh both the public message and the admin dashboard."""
    async with async_session_maker() as session:
        game = await session.get(Game, game_id)
        if not game:
            return

        from app.bot.utils import update_game_message
        try:
            await update_game_message(bot, game, session)
        except Exception as e:
            logger.warning(f"Failed to update game messages for game {game_id}: {e}")

        from app.bot.admin_dashboard import update_dashboard_message
        try:
            await update_dashboard_message(bot, game_id, session)
        except Exception as e:
            logger.warning(f"Failed to update dashboard for game {game_id}: {e}")


async def _refresh_public_message(game_id: int):
    """Refresh only the public group/channel message."""
    async with async_session_maker() as session:
        game = await session.get(Game, game_id)
        if not game:
            return

        from app.bot.utils import update_game_message
        try:
            await update_game_message(bot, game, session)
        except Exception as e:
            logger.warning(f"Failed to update game messages for game {game_id}: {e}")


# Keep for backward-compat with any code that calls update_game_ui directly
async def update_game_ui(game_id: int):
    await _refresh_full(game_id)
