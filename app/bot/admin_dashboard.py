
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from app.db.models import Game, Signup, Chat, SignupStatus, User
from app.config import settings

async def update_dashboard_message(bot: Bot, game_id: int, session: AsyncSession):
    """
    Updates (or sends) the Admin Dashboard message in the linked Admin Chat.
    """
    # 1. Fetch Game with Chat
    result = await session.execute(
        select(Game).where(Game.id == game_id)
    )
    game = result.scalar_one_or_none()
    if not game:
        return

    # Check if this game's chat has a linked Admin Chat
    chat_result = await session.get(Chat, game.chat_id)
    if not chat_result or not chat_result.admin_chat_id:
        return # No admin chat linked, do nothing
    
    admin_chat_id = chat_result.admin_chat_id

    # 2. Fetch Signups with Users
    stmt = select(Signup, User).join(User).where(Signup.game_id == game_id).where(Signup.status == SignupStatus.ACTIVE).order_by(Signup.created_at)
    res = await session.execute(stmt)
    rows = res.all() # [(Signup, User), ...]
    
    # 3. Format Text
    text = f"🎮 <b>Управление Игрой #{game.id}</b>\n"
    text += f"📍 {game.location} | {game.date_time.strftime('%H:%M')}\n"
    text += f"👥 Игроков: {len(rows)}/{game.max_players}\n\n"
    text += "🔽 <i>Нажмите на игрока, чтобы подтвердить оплату</i>"

    # 4. Build Keyboard (Grid of Players + Actions)
    buttons = []
    
    # Player Buttons
    current_row = []
    for signup, user in rows:
        status_icon = "✅" if signup.is_paid else "🔴"
        # Truncate Name if too long
        name = user.full_name[:12] + ".." if len(user.full_name) > 12 else user.full_name
        btn_text = f"{status_icon} {name}"
        cb_data = f"toggle_pay_{signup.id}"
        
        current_row.append(InlineKeyboardButton(text=btn_text, callback_data=cb_data))
        
        if len(current_row) == 2:
            buttons.append(current_row)
            current_row = []
            
    if current_row:
        buttons.append(current_row)
        
    # Actions Row
    actions_row = []
    # Draft WebApp Button
    web_app_url = f"{settings.WEBAPP_URL}/web/draft.html?game_id={game.id}"
    actions_row.append(InlineKeyboardButton(text="🔀 Составы (Драфт)", web_app=WebAppInfo(url=web_app_url)))
    buttons.append(actions_row)
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    # 5. Send or Edit
    try:
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
                # "Message to edit not found"
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
            
    except Exception as e:
        print(f"Error updating admin dashboard: {e}")
