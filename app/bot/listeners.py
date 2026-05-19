"""
listeners.py — Bot-side event handlers.

Subscribes to domain events from core/events.py and reacts by updating
the Telegram UI. This module knows about the bot, but core/ does NOT.

The bot object is imported from instance.py (no circular deps).
"""
import logging
from app.core.events import (
    event_bus, GameStateChangedEvent, GameMessageNeedsUpdateEvent,
    GameCreatedEvent, GameFinishedEvent, GameUpdatedEvent, TeamsPublishedEvent,
)
from app.core.services.roster import PlayerJoinedEvent, PlayerLeftEvent
from app.bot.instance import bot
from app.db.database import async_session_maker
from app.db.models import Game

logger = logging.getLogger(__name__)


def setup_listeners():
    """Register all bot-side event handlers. Call once at startup."""
    event_bus.subscribe(GameStateChangedEvent, on_game_state_changed)
    event_bus.subscribe(GameMessageNeedsUpdateEvent, on_game_message_needs_update)
    event_bus.subscribe(GameCreatedEvent, on_game_created)
    event_bus.subscribe(GameFinishedEvent, on_game_finished)
    event_bus.subscribe(GameUpdatedEvent, on_game_updated)
    event_bus.subscribe(TeamsPublishedEvent, on_teams_published)
    event_bus.subscribe(PlayerJoinedEvent, on_player_joined)
    event_bus.subscribe(PlayerLeftEvent, on_player_left)
    logger.info("Event listeners registered.")


# ---------------------------------------------------------------------------
# Domain event handlers
# ---------------------------------------------------------------------------

async def on_game_created(event: GameCreatedEvent):
    """Handle new game: send message to chat, pin it, update dashboard."""
    if not event.should_publish:
        # Deferred publish or past game — just update dashboard
        await _refresh_dashboard(event.game_id)
        return

    async with async_session_maker() as session:
        game = await session.get(Game, event.game_id)
        if not game:
            return

        try:
            from app.bot.utils import format_game_message
            from app.bot.keyboards import get_game_keyboard

            # Check if chat is a channel
            try:
                chat_info = await bot.get_chat(event.chat_id)
                if chat_info.type == "channel":
                    game.channel_id = event.chat_id
            except Exception as e:
                logger.warning(f"Failed to check chat type: {e}")

            text = await format_game_message(game, session, is_short=False)
            msg = await bot.send_message(
                chat_id=game.chat_id,
                text=text,
                reply_markup=get_game_keyboard(game.id),
                parse_mode="HTML"
            )
            game.message_id = msg.message_id
            if game.channel_id == game.chat_id:
                game.channel_message_id = msg.message_id

            await session.commit()

            try:
                await bot.pin_chat_message(chat_id=game.chat_id, message_id=msg.message_id)
            except Exception:
                pass  # Pin may fail if bot lacks permissions

        except Exception as e:
            logger.warning(f"Failed to publish game {event.game_id} to chat: {e}")

    await _refresh_dashboard(event.game_id)


async def on_game_finished(event: GameFinishedEvent):
    """Send finish result text to chat, then refresh dashboard."""
    if event.result_text:
        try:
            await bot.send_message(
                chat_id=event.chat_id,
                text=event.result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Failed to send finish message for game {event.game_id}: {e}")

    # Clean up and close the MVP voting message if it exists
    async with async_session_maker() as session:
        game = await session.get(Game, event.game_id)
        if game and game.voting_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=game.chat_id,
                    message_id=game.voting_message_id,
                    text=f"Матч <b>#{game.id}</b> завершен.\n\n<b>Голосование за MVP закрыто!</b>\nРезультаты опубликованы ниже.",
                    reply_markup=None,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Failed to close voting message on game finish for game {event.game_id}: {e}")

    await _refresh_full(event.game_id)


async def on_game_updated(event: GameUpdatedEvent):
    """Edit public message if there were changes, then refresh dashboard."""
    if event.changes:
        await _refresh_public_message(event.game_id)
    await _refresh_dashboard(event.game_id)


async def on_teams_published(event: TeamsPublishedEvent):
    """Edit/send the public game message after teams are published."""
    async with async_session_maker() as session:
        game = await session.get(Game, event.game_id)
        if not game:
            return

        try:
            from app.bot.utils import format_game_message
            from app.bot.keyboards import get_game_keyboard

            public_text = await format_game_message(game, session)
            kb = get_game_keyboard(game.id)

            if game.message_id:
                try:
                    await bot.edit_message_text(
                        chat_id=game.chat_id,
                        message_id=game.message_id,
                        text=public_text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    err_str = str(e)
                    if "message is not modified" in err_str:
                        pass
                    elif any(x in err_str for x in [
                        "message to edit not found",
                        "message can't be edited",
                        "BUTTON_TYPE_INVALID"
                    ]):
                        msg = await bot.send_message(
                            chat_id=game.chat_id,
                            text=public_text,
                            reply_markup=kb,
                            parse_mode="HTML"
                        )
                        game.message_id = msg.message_id
                        await session.commit()
                    else:
                        raise e
            else:
                msg = await bot.send_message(
                    chat_id=game.chat_id,
                    text=public_text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                game.message_id = msg.message_id
                await session.commit()

            # Also update MVP voting message keyboard if voting is already open/created
            if game.voting_message_id:
                try:
                    from sqlalchemy import select
                    from app.db.models import User, Signup, SignupStatus, Team
                    
                    result = await session.execute(
                        select(User, Signup.team)
                        .join(Signup)
                        .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
                    )
                    players_data = result.all()
                    
                    team_a = []
                    team_b = []
                    for user, team in players_data:
                        if team == Team.A:
                            team_a.append(user)
                        elif team == Team.B:
                            team_b.append(user)
                    
                    from app.bot.keyboards import get_voting_keyboard
                    voting_kb = get_voting_keyboard(game.id, team_a, team_b)
                    
                    await bot.edit_message_reply_markup(
                        chat_id=game.chat_id,
                        message_id=game.voting_message_id,
                        reply_markup=voting_kb
                    )
                except Exception as ex:
                    logger.warning(f"Failed to update voting message keyboard for game {game.id}: {ex}")

        except Exception as e:
            logger.error(f"Failed to publish teams for game {event.game_id}: {e}", exc_info=True)

    await _refresh_dashboard(event.game_id)


# ---------------------------------------------------------------------------
# Roster event handlers
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
    await _refresh_public_message(game_id)
    await _refresh_dashboard(game_id)


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


async def _refresh_dashboard(game_id: int):
    """Refresh only the admin dashboard message."""
    async with async_session_maker() as session:
        from app.bot.admin_dashboard import update_dashboard_message
        try:
            await update_dashboard_message(bot, game_id, session)
        except Exception as e:
            logger.warning(f"Failed to update dashboard for game {game_id}: {e}")


# Keep for backward-compat
async def update_game_ui(game_id: int):
    await _refresh_full(game_id)
