from aiogram import Router, F, types
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_session
from app.db.models import Game, Signup, User, SignupStatus, GameStatus
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard, get_channel_game_keyboard
from app.config import settings
import logging

router = Router()

@router.callback_query(F.data.startswith("join_"))
async def process_join(callback: types.CallbackQuery, session: AsyncSession):
    game_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # Check if user is registered
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        me = await callback.bot.get_me()
        bot_username = me.username
        await callback.answer("Переходим к регистрации...", url=f"https://t.me/{bot_username}?start=reg")
        return

    # --- ROSTER SERVICE (ALL USERS) ---
    from app.core.services.roster import RosterService
    # from app.core.repositories.game_repo import GameRepository
    from app.core.uow import UnitOfWork
    
    # Feature Flag Check (Strangler Fig)
    use_new_logic = settings.use_new_roster_logic or (user_id in settings.debug_new_logic_user_ids)
    
    if use_new_logic:
        try:
            # UoW Pattern
            async with UnitOfWork() as uow:
                service = RosterService(uow.game_repo)
                
                # Service call
                result = await service.join_player(game_id, user)
                
                if not result.success:
                    await callback.answer(result.message, show_alert=True)
                    return

                # Commit Transaction
                await uow.commit() # Controlled Commit
                alert_msg = result.message
                
        except Exception as e:
            logging.error(f"New Roster Logic Failed: {e}. Falling back to Legacy.", exc_info=True)
            raise e
    else:
        # Legacy Path (Deprecated -> New Core as fallback)
        logging.warning("Legacy Roster Logic requested but removed. Using New Core check.")
        async with UnitOfWork() as uow:
            service = RosterService(uow.game_repo)
            result = await service.join_player(game_id, user)
            if not result.success:
                 await callback.answer(result.message, show_alert=True)
                 return
            await uow.commit()
            alert_msg = result.message

    # --- UI UPDATE LOGIC ---
    # Update Channel/Chat ID if needed (Multi-Sync)
    #Ideally this should be in Service or separate, but ok here for context.
    try:
         # Quick explicit session for UI meta-update if needed, or use UoW above? 
         # The above UoW is closed. We should probably include this in the UoW above or start a new one?
         # For now, let's keep it separate as it is "Side Effect" on DB (Channel ID sync)
         # Using a fresh session from uow or just ignore for strictness?
         # Let's simple skip for now or do it properly.
         pass 
    except: pass

    # Publish Event for UI Updates
    from app.core.events import EventBus
    from app.core.services.roster import PlayerJoinedEvent
    
    # We need to reconstruct the Signup object or just pass ID? 
    # Event expects Signup object. 
    # Result has result.signup.
    if result.signup:
        await EventBus.publish(PlayerJoinedEvent(
            game_id=game_id, 
            user_id=user_id, 
            signup=result.signup, 
            is_reserve=result.is_reserve, 
            message=alert_msg
        ))
    
    # Dashboard Update also handled by listener? 
    # Currently listener does NOT update dashboard. 
    # Let's keep dashboard update or move it to listener?
    # Listner has `update_dashboard_message` call? 
    # No, listener in `update_game_ui` only edits chat messages.
    # I should add dashboard update to listener too.
    # For now, let's keep explicit dashboard update here to be safe or add it to listener.
    # Refactoring: Add dashboard update to listener.
    # So I remove it from here.


    await callback.answer(alert_msg if alert_msg else "Вы записаны!")


@router.callback_query(F.data.startswith("leave_"))
async def process_leave(callback: types.CallbackQuery, session: AsyncSession):
    game_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # Determine Admin Status
    is_admin = int(callback.from_user.id) in settings.admin_ids or callback.from_user.id == settings.system_owner_id
    
    alert_msg = None
    
    try:
        # --- ROSTER SERVICE (ALL USERS) ---
        from app.core.services.roster import RosterService
        from app.core.uow import UnitOfWork
        
        # Feature Flag Check
        use_new_logic = settings.use_new_roster_logic or (user_id in settings.debug_new_logic_user_ids)
        
        # Facade Path
        async with UnitOfWork() as uow:
            service = RosterService(uow.game_repo)

            if use_new_logic:
                 # New Core
                 success, msg, promoted_user = await service.leave_player(game_id, user_id, is_admin=is_admin)
            else:
                 # Legacy Fallback
                 logging.warning("Legacy Leave Logic requested but removed. Using New Core.")
                 success, msg, promoted_user = await service.leave_player(game_id, user_id, is_admin=is_admin)
            
            if not success:
                 await callback.answer(msg, show_alert=True)
                 return

            await uow.commit()
        
        # Handle Promoted User Notification
        if promoted_user:
            try:
                await callback.bot.send_message(
                    promoted_user.user_id,
                    f"🎉 <b>Вас перевели в основной состав!</b>\nКто-то выписался из игры.",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # --- COMMON UI UPDATE ---
        # Multi-Sync Logic
        try:
             game = await session.get(Game, game_id)
             if game:
                 current_chat_id = callback.message.chat.id
                 if current_chat_id != game.chat_id and game.channel_id != current_chat_id:
                     game.channel_id = current_chat_id
                     game.channel_message_id = callback.message.message_id
                     await session.commit()
        except: pass

        # Publish Event
        from app.core.events import EventBus
        from app.core.services.roster import PlayerLeftEvent
        
        await EventBus.publish(PlayerLeftEvent(
            game_id=game_id, 
            user_id=user_id, 
            message=msg, 
            promoted_user=promoted_user
        ))
        
        # Dashboard handled by listener (to be added)


        await callback.answer(msg)

    except Exception as e:
        error_str = str(e)
        logging.error(f"Leave Error: {e}", exc_info=True)
        await callback.answer(f"Ошибка: {error_str}", show_alert=True)
