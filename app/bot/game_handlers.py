from aiogram import Router, F, types
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_session
from app.db.models import Game, Signup, User, SignupStatus, GameStatus
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard
from app.config import settings
import logging

router = Router()

@router.callback_query(F.data.startswith("join_"))
async def process_join(callback: types.CallbackQuery, session: AsyncSession):
    game_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # Check if user is registered (basic check before Service call, or let Service handle?)
    # Service expects user to exist.
    # existing check logic kept for UX (redirect to reg)
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        me = await callback.bot.get_me()
        bot_username = me.username
        await callback.answer("Переходим к регистрации...", url=f"https://t.me/{bot_username}?start=reg")
        return

    from app.services.game_service import GameService, GameActionError, GameFullError, AlreadySignedUpError
    
    game_service = GameService(session)
    
    try:
        signup, alert_msg = await game_service.join_game(game_id, user_id)
        
        # Success! Update UI
        game = await game_service.get_game(game_id)
        text = await format_game_message(game, session)
        
        # --- Multi-Sync Logic ---
        current_chat_id = callback.message.chat.id
        if current_chat_id != game.chat_id:
            if game.channel_id != current_chat_id:
                game.channel_id = current_chat_id
                game.channel_message_id = callback.message.message_id
                await session.commit()

        # Update Both Messages
        async def safe_edit(chat_id, msg_id):
            if not chat_id or not msg_id: return
            try:
                await callback.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text,
                    reply_markup=get_game_keyboard(game_id),
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"Failed to edit message in {chat_id}: {e}")

        await safe_edit(game.chat_id, game.message_id) # Primary
        await safe_edit(game.channel_id, game.channel_message_id) # Channel

        # Dashboard Update
        from app.bot.admin_dashboard import update_dashboard_message
        try:
             await update_dashboard_message(callback.bot, game.id, session)
        except Exception as e:
             logging.warning(f"Failed to update dashboard: {e}")

        await callback.answer(alert_msg if alert_msg else "Вы записаны!")

    except AlreadySignedUpError:
        await callback.answer("Вы уже записаны!")
        # Optional: Refresh message
    except GameActionError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logging.error(f"Join Error: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при записи.")

@router.callback_query(F.data.startswith("leave_"))
async def process_leave(callback: types.CallbackQuery, session: AsyncSession):
    game_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    from app.services.game_service import GameService, GameActionError, CancellationLockedError
    
    game_service = GameService(session)
    # Refined admin check including strings if necessary, though IDs should be ints
    is_admin = int(callback.from_user.id) in settings.admin_ids or callback.from_user.id == settings.system_owner_id
    logging.warning(f"DEBUG_LEAVE: user={callback.from_user.id} game={game_id} is_admin={is_admin}")
    
    try:
        game, was_active = await game_service.leave_game(game_id, user_id, is_admin=is_admin)
        
        # Success! Update UI
        text = await format_game_message(game, session)
        
        # --- Multi-Sync Logic ---
        current_chat_id = callback.message.chat.id
        if current_chat_id != game.chat_id:
            if game.channel_id != current_chat_id:
                game.channel_id = current_chat_id
                game.channel_message_id = callback.message.message_id
                await session.commit()

        async def safe_edit(chat_id, msg_id):
            if not chat_id or not msg_id: return
            try:
                await callback.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text,
                    reply_markup=get_game_keyboard(game_id),
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"Failed to edit message in {chat_id}: {e}")

        await safe_edit(game.chat_id, game.message_id)
        await safe_edit(game.channel_id, game.channel_message_id)
        
        # Trigger Admin Dashboard Update
        from app.bot.admin_dashboard import update_dashboard_message
        try:
             await update_dashboard_message(callback.bot, game.id, session)
        except Exception as e:
             logging.warning(f"Failed to update dashboard: {e}")

        await callback.answer("Вы выписались.")

    except CancellationLockedError as e:
        # Notify Admin Chat
        chat_id = callback.message.chat.id
        user_name = callback.from_user.full_name
        
        # Try to find admin chat
        try:
             chat_stmt = select(Chat).where(Chat.chat_id == game_id) # Wait, game.chat_id
             # We need game object here. Let's fetch it if error occurs or fetch before.
             # Actually we can just inform the chat where button was clicked if it's admin or get it from Chat model
             from app.db.models import Game, Chat
             game_obj = await session.get(Game, game_id)
             if game_obj:
                 chat_obj = await session.get(Chat, game_obj.chat_id)
                 if chat_obj and chat_obj.admin_chat_id:
                     await callback.bot.send_message(
                         chat_obj.admin_chat_id,
                         f"⚠️ <b>Попытка отмены!</b>\nИгрок <a href='tg://user?id={user_id}'>{user_name}</a> пытался выписаться из игры #{game_id}, но уже слишком поздно.",
                         parse_mode="HTML"
                     )
        except Exception as ex:
             logging.warning(f"Failed to notify admin of late cancellation: {ex}")

        await callback.answer(str(e), show_alert=True)
    except GameActionError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logging.error(f"Leave Error: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при отмене записи.")
