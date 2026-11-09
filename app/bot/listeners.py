"""
listeners.py — Bot-side event handlers.

Subscribes to domain events from core/events.py and reacts by updating
the Telegram UI. This module knows about the bot, but core/ does NOT.
"""
import asyncio
import html
import logging
import time
from typing import Awaitable, Callable, Dict

from app.bot.instance import bot
from app.core.events import (
    GameCreatedEvent,
    GameFinishedEvent,
    GameMessageNeedsUpdateEvent,
    GameStateChangedEvent,
    GameUpdatedEvent,
    TeamsPublishedEvent,
    event_bus,
)
from app.core.services.roster import PlayerJoinedEvent, PlayerLeftEvent
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


async def on_game_created(event: GameCreatedEvent):
    """Handle new game: send message to chat and pin it."""
    if not event.should_publish:
        await _refresh_dashboard(event.game_id)
        return

    async with async_session_maker() as session:
        game = await session.get(Game, event.game_id)
        if not game:
            return

        try:
            from app.bot.keyboards import get_channel_game_keyboard, get_game_keyboard
            from app.bot.utils import format_game_message, resolve_chat_language

            is_channel = False
            try:
                chat_info = await bot.get_chat(event.chat_id)
                if chat_info.type == "channel":
                    game.channel_id = event.chat_id
                    is_channel = True
            except Exception as e:
                logger.warning(f"Failed to check chat type: {e}")

            chat_lang = await resolve_chat_language(session, game.chat_id)
            text = await format_game_message(
                game, session, is_short=False, lang=chat_lang
            )

            # Publish to linked channel if distinct from main group
            if game.channel_id and game.channel_id != game.chat_id:
                try:
                    ch_kb = get_channel_game_keyboard(game.id, lang=chat_lang)
                    ch_msg = await bot.send_message(
                        chat_id=game.channel_id,
                        text=text,
                        reply_markup=ch_kb,
                        parse_mode="HTML",
                    )
                    game.channel_message_id = ch_msg.message_id
                except Exception as e:
                    logger.warning(f"Failed to publish to channel {game.channel_id}: {e}")

            # For group chat, use get_game_keyboard (opens WebApp in-app without redirecting to PM)
            kb = (
                get_channel_game_keyboard(game.id, lang=chat_lang)
                if is_channel
                else get_game_keyboard(game.id, is_admin=False, lang=chat_lang, include_rules=True)
            )

            msg = await bot.send_message(
                chat_id=game.chat_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            game.message_id = msg.message_id
            if game.channel_id == game.chat_id:
                game.channel_message_id = msg.message_id

            await session.commit()

            try:
                await bot.pin_chat_message(
                    chat_id=game.chat_id, message_id=msg.message_id
                )
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Failed to publish game {event.game_id} to chat: {e}")

    await _refresh_dashboard(event.game_id)
async def on_game_finished(event: GameFinishedEvent):
    """Send finish result text to chat and unpin match post (voting remains open)."""
    if event.result_text:
        try:
            await bot.send_message(
                chat_id=event.chat_id,
                text=event.result_text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Failed to send finish message for game {event.game_id}: {e}")

    async with async_session_maker() as session:
        game = await session.get(Game, event.game_id)
        if game:
            if game.chat_id and game.message_id:
                try:
                    await bot.unpin_chat_message(
                        chat_id=game.chat_id, message_id=game.message_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to unpin message for game {event.game_id}: {e}")

            if game.channel_id and game.channel_message_id:
                try:
                    await bot.unpin_chat_message(
                        chat_id=game.channel_id, message_id=game.channel_message_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to unpin channel message for game {event.game_id}: {e}")

            # Trigger voting if not yet opened
            if not game.voting_message_id:
                try:
                    from app.scheduler.tasks import send_voting_message
                    await send_voting_message(game.id)
                except Exception as e:
                    logger.warning(f"Failed to trigger voting on game finish: {e}")

    await _refresh_full(event.game_id)
async def on_game_updated(event: GameUpdatedEvent):
    """Edit public message if there were changes."""
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
            from app.bot.keyboards import get_channel_game_keyboard, get_game_keyboard
            from app.bot.utils import format_game_message, resolve_chat_language

            chat_lang = await resolve_chat_language(session, game.chat_id)
            public_text = await format_game_message(game, session, lang=chat_lang)
            is_chan = (game.channel_id == game.chat_id)
            kb = get_channel_game_keyboard(game.id, lang=chat_lang) if is_chan else get_game_keyboard(game.id, is_admin=False, lang=chat_lang, include_rules=True)

            if game.message_id:
                try:
                    await bot.edit_message_text(
                        chat_id=game.chat_id,
                        message_id=game.message_id,
                        text=public_text,
                        reply_markup=kb,
                        parse_mode="HTML",
                    )
                except Exception as e:
                    err_str = str(e)
                    if "message is not modified" in err_str:
                        pass
                    elif any(
                        x in err_str
                        for x in [
                            "message to edit not found",
                            "message can't be edited",
                            "BUTTON_TYPE_INVALID",
                        ]
                    ):
                        msg = await bot.send_message(
                            chat_id=game.chat_id,
                            text=public_text,
                            reply_markup=kb,
                            parse_mode="HTML",
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
                    parse_mode="HTML",
                )
                game.message_id = msg.message_id
                await session.commit()

            if game.voting_message_id:
                try:
                    from sqlalchemy import select
                    from app.bot.keyboards import get_voting_keyboard
                    from app.db.models import Signup, SignupStatus, Team, User

                    result = await session.execute(
                        select(User, Signup.team)
                        .join(Signup)
                        .where(
                            Signup.game_id == game.id,
                            Signup.status == SignupStatus.ACTIVE,
                        )
                    )
                    players_data = result.all()

                    team_a = [u for u, t_enum in players_data if t_enum == Team.A]
                    team_b = [u for u, t_enum in players_data if t_enum == Team.B]
                    team_c = [u for u, t_enum in players_data if t_enum == Team.C]

                    voting_kb = get_voting_keyboard(
                        game.id, team_a, team_b, team_c=team_c, lang=chat_lang
                    )

                    await bot.edit_message_reply_markup(
                        chat_id=game.chat_id,
                        message_id=game.voting_message_id,
                        reply_markup=voting_kb,
                    )
                except Exception as ex:
                    logger.warning(
                        f"Failed to update voting message keyboard for game {game.id}: {ex}"
                    )

        except Exception as e:
            logger.error(
                f"Failed to publish teams for game {event.game_id}: {e}", exc_info=True
            )

    await _refresh_dashboard(event.game_id)


async def on_game_state_changed(event: GameStateChangedEvent):
    await _refresh_full(event.game_id)


async def on_game_message_needs_update(event: GameMessageNeedsUpdateEvent):
    await _refresh_public_message(event.game_id)


async def on_player_joined(event: PlayerJoinedEvent):
    await _refresh_full(event.game_id)


async def on_player_left(event: PlayerLeftEvent):
    if event.promoted_user:
        try:
            async with async_session_maker() as session:
                game = await session.get(Game, event.game_id)
                game_num = event.game_id
                date_str = ""
                loc_str = ""
                if game:
                    from app.bot.utils import get_group_game_number
                    from app.core.timezone import format_prague_dt

                    game_num = await get_group_game_number(session, game)
                    date_str = format_prague_dt(game.date_time)
                    loc_str = game.location or ""

                from app.bot.i18n import t
                from app.bot.utils import resolve_chat_language

                p_lang = await resolve_chat_language(
                    session, game.chat_id if game else None
                )
                p_text = t(
                    "promoted_auto",
                    locale=p_lang,
                    game_num=game_num,
                    location=html.escape(loc_str),
                    date=date_str,
                )
                await bot.send_message(
                    event.promoted_user.user_id,
                    p_text,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.warning(f"Failed to notify promoted user: {e}")
    await _refresh_full(event.game_id)


async def _refresh_full(game_id: int):
    await _refresh_public_message(game_id)
    await _refresh_dashboard(game_id)


class TelegramRenderDebouncer:
    """
    Per-game coalescing rate-limiter for Telegram `edit_message_text` calls (ADR-05).
    Prevents HTTP 429 Too Many Requests during flash-crowd signups by enforcing a
    minimum interval between public message edits per game (`cooldown_seconds=3.2s`
    -> <= 18 edits/min/chat, safely below Telegram's 20 edits/min/group ceiling).
    - First call outside the window executes immediately (leading edge).
    - Subsequent calls within the window coalesce into a single trailing refresh.
    """

    def __init__(
        self,
        render_fn: Callable[[int], Awaitable[None]],
        cooldown_seconds: float = 3.2,
        redis_client: object = None,
    ):
        self._render_fn = render_fn
        self.cooldown_seconds = cooldown_seconds
        self._redis_client = redis_client
        self._last_run: Dict[int, float] = {}
        self._pending_tasks: Dict[int, asyncio.Task] = {}
        self._dirty: set[int] = set()
        self.coalesced_drops: int = 0

    async def _try_acquire_distributed_slot(self, game_id: int) -> bool:
        """
        Attempts to acquire a distributed Redis rate-limit token (`SET render_lock:game:{id} 1 PX ... NX`)
        so multiple worker processes or Kubernetes replicas never exceed the per-chat edit budget.
        Falls back gracefully to in-memory tracking when Redis is not attached.
        """
        if self._redis_client is None:
            return True
        try:
            px = max(100, int(self.cooldown_seconds * 1000))
            acquired = await self._redis_client.set(
                f"render_lock:game:{game_id}", "1", px=px, nx=True
            )
            return bool(acquired)
        except Exception:
            return True

    async def trigger(self, game_id: int) -> None:
        if self.cooldown_seconds <= 0:
            await self._render_fn(game_id)
            return

        now = time.monotonic()
        last = self._last_run.get(game_id)
        in_local_window = last is not None and (now - last) < self.cooldown_seconds

        # If a trailing task is already scheduled, we are inside the local cooldown window,
        # or another worker replica holds the distributed Redis slot, coalesce into trailing flush
        if (
            game_id in self._pending_tasks
            or in_local_window
            or not await self._try_acquire_distributed_slot(game_id)
        ):
            self._dirty.add(game_id)
            self.coalesced_drops += 1
            if game_id not in self._pending_tasks:
                delay = max(
                    0.01,
                    self.cooldown_seconds - (now - last)
                    if in_local_window and last is not None
                    else self.cooldown_seconds,
                )
                self._pending_tasks[game_id] = asyncio.create_task(
                    self._delayed_flush(game_id, delay)
                )
            return

        # Leading-edge immediate execution
        self._last_run[game_id] = now
        await self._render_fn(game_id)

    async def _delayed_flush(self, game_id: int, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            if game_id in self._dirty:
                self._dirty.discard(game_id)
                self._last_run[game_id] = time.monotonic()
                await self._render_fn(game_id)
        finally:
            self._pending_tasks.pop(game_id, None)


async def _do_refresh_public_message(game_id: int):
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


render_debouncer = TelegramRenderDebouncer(_do_refresh_public_message, cooldown_seconds=3.2)


async def _refresh_public_message(game_id: int):
    """Coalesced refresh of the public group/channel message."""
    await render_debouncer.trigger(game_id)


async def _refresh_dashboard(game_id: int):
    """No-op hook retained for backward compatibility with WebApp dashboard model."""
    return


async def update_game_ui(game_id: int):
    await _refresh_full(game_id)
