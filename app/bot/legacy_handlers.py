from aiogram import Router, F, types
from app.bot.utils import format_game_message
from app.config import settings
from app.core.uow import UnitOfWork
from app.core.services.legacy_roster import LegacyRosterService, JoinResult
from app.core.services.legacy_roster import PlayerJoinedEvent, PlayerLeftEvent # Keep event classes if they are in legacy_roster
# Actually, I should check if legacy_roster has them. `git show` HEAD~1 had them.
# But wait, HEAD~1 roster.py had them? 
# Yes, checking view_file earlier.
# But I need to be sure. I'll read legacy_roster.py content first to be 100% sure before Replace.

# Temporary content placeholder, will verify file first. # Assuming these classes are in roster.py or need to be moved to events?
# Wait, user's roster.py code did NOT include Event classes. 
# I need to ensure Event classes are defined somewhere. 
# They were in roster.py before. User's snippet for roster.py removed them?
# Let me check my previous view of roster.py. 
# Yes, they were in roster.py. User's provided code for roster.py did NOT have them.
# They should be in app/core/events.py or roster.py. 
# User said "Refactor RosterService: Rewrite app/core/services/roster.py".
# If I overwrite roster.py with user's code, I lose Event definitions if they were there.
# I should move them to events.py or keep them in roster.py.
# User's code has `from app.core.services.roster import RosterService, PlayerJoinedEvent, PlayerLeftEvent` in handlers.
# So they expect them in roster.py probably.
# I will append them to roster.py or ensure they are there.

from app.core.events import event_bus, Event
import logging

router = Router()

@router.callback_query(F.data.startswith("join_"))
async def process_join(callback: types.CallbackQuery):
    game_id = int(callback.data.split("_")[1])
    telegram_user_id = callback.from_user.id
    
    alert_msg = None
    event_payload = None

    try:
        # Open Transaction
        async with UnitOfWork() as uow:
            # 1. Get User via Repo (No Raw SQL)
            user = await uow.user_repo.get_by_id(telegram_user_id)
            
            if not user:
                me = await callback.bot.get_me()
                bot_username = me.username
                await callback.answer("Регистрация обязательна!", url=f"https://t.me/{bot_username}?start=reg")
                return

            # 2. Init Service
            service = RosterService(uow)
            
            # 3. Biz Logic
            result = await service.join_player(game_id, user)
            
            if not result.success:
                await callback.answer(result.message, show_alert=True)
                return # Rollback auto

            alert_msg = result.message

            # Prepare Event (After Commit)
            if result.signup:
                # We need to import PlayerJoinedEvent. 
                # Assuming it is available.
                from app.core.services.roster import PlayerJoinedEvent
                event_payload = PlayerJoinedEvent(
                    game_id=game_id,
                    user_id=telegram_user_id,
                    signup=result.signup,
                    is_reserve=result.is_reserve,
                    message=alert_msg
                )

            # 4. Commit Atomically
            await uow.commit()

        # --- Side Effects ---
        if event_payload:
            await event_bus.publish(event_payload)

        await callback.answer(alert_msg)

    except Exception as e:
        logging.error(f"Join Error: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при записи.", show_alert=True)


@router.callback_query(F.data.startswith("leave_"))
async def process_leave(callback: types.CallbackQuery):
    game_id = int(callback.data.split("_")[1])
    telegram_user_id = callback.from_user.id
    is_admin = telegram_user_id in settings.admin_ids or telegram_user_id == settings.system_owner_id
    
    promoted_user = None
    msg = ""
    success = False

    try:
        async with UnitOfWork() as uow:
            service = RosterService(uow)
            
            success, msg, promoted_user = await service.leave_player(
                game_id, telegram_user_id, is_admin=is_admin
            )
            
            if not success:
                await callback.answer(msg, show_alert=True)
                return

            # Update Chat Metadata (Sync Logic)
            game = await uow.game_repo.get_game(game_id)
            if game:
                 current_chat_id = callback.message.chat.id
                 if current_chat_id != game.chat_id and game.channel_id != current_chat_id:
                     game.channel_id = current_chat_id
                     game.channel_message_id = callback.message.message_id
                     # Session tracks game, commit will save it.

            await uow.commit()
        
        # --- Post-Commit Actions ---
        
        # Notify Promoted User
        if promoted_user:
            try:
                await callback.bot.send_message(
                    promoted_user.user_id,
                    "🎉 <b>Вас перевели в основной состав!</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass # Non-blocking

        # Publish Event
        from app.core.services.roster import PlayerLeftEvent
        await event_bus.publish(PlayerLeftEvent(
            game_id=game_id, 
            user_id=telegram_user_id, 
            message=msg, 
            promoted_user=promoted_user
        ))

        await callback.answer(msg)

    except Exception as e:
        logging.error(f"Leave Error: {e}", exc_info=True)
        await callback.answer("Ошибка при выходе.", show_alert=True)
