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
    from app.core.repositories.game_repo import GameRepository
    
    repo = GameRepository(session)
    service = RosterService(repo)
    
    # Service call
    result = await service.join_player(game_id, user)
    
    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return

    # Commit Transaction
    await session.commit()
    alert_msg = result.message

    # --- UI UPDATE LOGIC ---
    try:
        # Fetch Game for UI
        game = await session.get(Game, game_id)
        if not game: return

        text = await format_game_message(game, session)
        
        # --- Multi-Sync Logic ---
        current_chat_id = callback.message.chat.id
        if current_chat_id != game.chat_id:
            if game.channel_id != current_chat_id:
                game.channel_id = current_chat_id
                game.channel_message_id = callback.message.message_id
                await session.commit()

        # Update Both Messages
        async def safe_edit(chat_id, msg_id, keyboard):
            if not chat_id or not msg_id: return
            try:
                await callback.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"Failed to edit message in {chat_id}: {e}")

        await safe_edit(game.chat_id, game.message_id, get_game_keyboard(game_id)) # Primary
        await safe_edit(game.channel_id, game.channel_message_id, get_channel_game_keyboard(game_id)) # Channel

        # Dashboard Update
        from app.bot.admin_dashboard import update_dashboard_message
        try:
                await update_dashboard_message(callback.bot, game.id, session)
        except Exception as e:
                logging.warning(f"Failed to update dashboard: {e}")

        await callback.answer(alert_msg if alert_msg else "Вы записаны!")
        
    except Exception as e:
         logging.error(f"UI Update Error: {e}", exc_info=True)
         if not alert_msg:
             await callback.answer("Записан, но не удалось обновить сообщение.")

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
        from app.core.repositories.game_repo import GameRepository
        
        repo = GameRepository(session)
        service = RosterService(repo)
        
        # Pass is_admin to service to determine if we can bypass locking
        success, msg, promoted_user = await service.leave_player(game_id, user_id, is_admin=is_admin)
        
        if not success:
             await callback.answer(msg, show_alert=True)
             
             # Notify Admin if it was a late cancellation attempt by a regular user
             if not is_admin and ("поздно" in msg.lower() or "lock" in msg.lower()):
                 try:
                     game_obj = await session.get(Game, game_id)
                     chat_obj = await session.get(Chat, game_obj.chat_id) if game_obj else None
                     if chat_obj and chat_obj.admin_chat_id:
                         await callback.bot.send_message(
                             chat_obj.admin_chat_id,
                             f"⚠️ <b>Попытка отмены!</b>\nИгрок <a href='tg://user?id={user_id}'>{callback.from_user.full_name}</a> пытался выписаться, но поздно.",
                             parse_mode="HTML"
                         )
                 except: pass
             return

        await session.commit()
        
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
        game = await session.get(Game, game_id)
        if not game:
             await callback.answer("Игра не найдена / Ошибка данных.")
             return

        text = await format_game_message(game, session)
        
        # --- Multi-Sync Logic ---
        current_chat_id = callback.message.chat.id
        if current_chat_id != game.chat_id:
            if game.channel_id != current_chat_id:
                game.channel_id = current_chat_id
                game.channel_message_id = callback.message.message_id
                await session.commit()

        async def safe_edit(chat_id, msg_id, keyboard):
            if not chat_id or not msg_id: return
            try:
                await callback.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"Failed to edit message in {chat_id}: {e}")

        await safe_edit(game.chat_id, game.message_id, get_game_keyboard(game_id))
        await safe_edit(game.channel_id, game.channel_message_id, get_channel_game_keyboard(game_id))
        
        # Trigger Admin Dashboard Update
        from app.bot.admin_dashboard import update_dashboard_message
        try:
             await update_dashboard_message(callback.bot, game.id, session)
        except Exception as e:
             logging.warning(f"Failed to update dashboard: {e}")

        await callback.answer(msg)

    except Exception as e:
        error_str = str(e)
        logging.error(f"Leave Error: {e}", exc_info=True)
        await callback.answer(f"Ошибка: {error_str}", show_alert=True)
