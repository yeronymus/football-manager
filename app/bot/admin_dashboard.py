
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from app.db.models import Game, Signup, Chat, SignupStatus, User
from app.config import settings
import logging
import html

async def update_dashboard_message(bot: Bot, game_id: int, session: AsyncSession, target_chat_id: int = None) -> bool:
    """
    Updates (or sends) the Admin Dashboard message in the linked Admin Chat.
    If target_chat_id is provided, it overrides the DB lookup.
    Returns True if dashboard was sent/updated.
    """
    try:
        # 1. Fetch Game with Chat
        logging.warning(f"DEBUG: update_dashboard START game_id={game_id}")
        result = await session.execute(
            select(Game).where(Game.id == game_id)
        )
        game = result.scalar_one_or_none()
        if not game:
            logging.warning(f"DEBUG: Game {game_id} not found")
            return False
            
        await session.refresh(game) # CRITICAL: Refresh BEFORE accessing any attributes

        admin_chat_id = target_chat_id
        # Only reset if it's a DIFFERENT chat
        if admin_chat_id and game.admin_message_id and admin_chat_id != game.chat_id:
             # Wait, game.chat_id is the group. game.admin_chat_id (effectively) is what we track.
             # Actually we don't store admin_chat_id in Game.
             pass
        
        if not admin_chat_id:
            # Check if this game's chat has a linked Admin Chat
            chat_result = await session.get(Chat, game.chat_id)
            if not chat_result or not chat_result.admin_chat_id:
                logging.warning(f"DEBUG: No linked admin chat for game {game_id}")
                return False # No admin chat linked, do nothing
            admin_chat_id = chat_result.admin_chat_id
        
        logging.warning(f"DEBUG: update_dashboard gID={game_id} gameChat={game.chat_id} target={admin_chat_id}")

        # 2. Fetch Signups with Users (Freshly)
        stmt = (
            select(Signup, User)
            .join(User)
            .where(Signup.game_id == game_id)
            .execution_options(populate_existing=True)
            .order_by(Signup.created_at)
        )
        res = await session.execute(stmt)
        all_rows = res.all() # [(Signup, User), ...]
        
        # Filter in Python to match utils.py logic and avoid SQL enum issues
        rows = [
            (s, u) for s, u in all_rows 
            if s.status in [SignupStatus.ACTIVE, SignupStatus.RESERVE]
        ]
        
        # Detailed Logging for debugging empty lists
        logging.warning(f"DEBUG_DASHBOARD: Game {game_id} - Fetched {len(rows)} active rows.")
        if len(rows) == 0:
            # Check for ANY signups for this game (not just active)
            count_res = await session.execute(select(func.count(Signup.id)).where(Signup.game_id == game_id))
            total_count = count_res.scalar()
            logging.warning(f"DEBUG_DASHBOARD: Total signups (any status) for game {game_id}: {total_count}")
        else:
            for s, u in rows:
                logging.warning(f"DEBUG_DASHBOARD: Found Active Signup ID {s.id} for user {u.full_name} (ID: {u.user_id})")
        
        # 3. Format Text
        try:
            loc = str(game.location) if game.location else "Unknown"
            loc_escaped = html.escape(loc)
            from datetime import timedelta
            local_dt = game.date_time + timedelta(hours=1)
            dt_str = local_dt.strftime('%d.%m %H:%M') if game.date_time else "??"
            
            # Status
            status_map = {
                "open": "🟢 Набор открыт",
                "active": "⚽ Игра активна",
                "finished": "🏁 Завершена",
                "cancelled": "❌ Отменена"
            }
            status_text = status_map.get(game.status.value, game.status.value)
            
            # Stats
            paid_count = sum(1 for s, u in rows if s.is_paid)
            
            text = f"🎮 <b>Управление Игрой #{game.id}</b>\n"
            text += f"📍 {loc_escaped} | 📅 {dt_str}\n"
            text += f"� {status_text}\n"
            text += f"�👥 Игроков: {len(rows)}/{game.max_players} | 💰 Оплачено: {paid_count}\n\n"
            text += "🔽 <i>Нажмите на имя для смены статуса оплаты:</i>"
        except Exception as e:
            logging.error(f"Error formatting dashboard text: {e}")
            text = f"🎮 <b>Game #{game.id}</b>\nError formatting details."

        logging.warning(f"DEBUG_DASHBOARD_TEXT: {text!r}")

        # 4. Build Keyboard (Grid of Players + Actions)
        buttons = []
        
        # Player Buttons (Grid 2xN for payment toggles)
        current_row = []
        for signup, user in rows:
            status_icon = "🟢" if signup.is_paid else "🔴"
            # Truncate Name
            name = user.full_name[:12] + ".." if len(user.full_name) > 12 else user.full_name
            btn_text = f"{status_icon} {name}"
            cb_data = f"toggle_pay_{signup.id}"
            
            current_row.append(InlineKeyboardButton(text=btn_text, callback_data=cb_data))
            
            if len(current_row) == 2:
                buttons.append(current_row)
                current_row = []
                
        if current_row:
            buttons.append(current_row)
            
        # Action Rows
        # Row 1: Edit, Draft
        row_1 = []
        edit_url = f"{settings.webapp_url}/web/edit_game.html?game_id={game.id}"
        # Fallback to URL to avoid BUTTON_TYPE_INVALID in groups/channels
        row_1.append(InlineKeyboardButton(text="✏️ Изменить", url=edit_url))
        
        draft_url = f"{settings.webapp_url}/web/draft.html?game_id={game.id}"
        row_1.append(InlineKeyboardButton(text="🔀 Составы (Draft)", url=draft_url))
        buttons.append(row_1)
        
        # Row 2: Kick Menu, Finish
        row_2 = []
        row_2.append(InlineKeyboardButton(text="💣 Убрать игрока", callback_data=f"god_kick_menu_{game.id}"))
        
        finish_url = f"{settings.webapp_url}/web/finish.html?game_id={game.id}"
        row_2.append(InlineKeyboardButton(text="🏁 Завершить матч", url=finish_url))
        buttons.append(row_2)
        
        # Row 3: Delete
        # Reuse God Mode logic for consistency
        row_3 = []
        row_3.append(InlineKeyboardButton(text="🧨 Удалить игру", callback_data=f"god_del_wait_{game.id}"))
        buttons.append(row_3)
        
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        # 5. Send or Edit
        if game.admin_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=admin_chat_id,
                    message_id=game.admin_message_id,
                    text=text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except Exception as e:
                # If message deleted or too old, resend?
                if "message to edit not found" in str(e).lower():
                    game.admin_message_id = None # Reset to resend
        
        if not game.admin_message_id:
            msg = await bot.send_message(
                chat_id=admin_chat_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML"
            )
            game.admin_message_id = msg.message_id
            await session.commit()
            
        return True
    except Exception as e:
        logging.error(f"CRITICAL ERROR updating dashboard: {e}", exc_info=True)
        try:
            target = target_chat_id or admin_chat_id
            if target:
                await bot.send_message(target, f"⚠️ <b>Dashboard Error:</b>\n{html.escape(str(e))}", parse_mode="HTML")
        except:
            pass
        return False
