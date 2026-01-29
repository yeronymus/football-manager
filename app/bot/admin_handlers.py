from aiogram import Router, F, types
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Game, Signup, User, SignupStatus, GameStatus, Team, Chat
from app.config import settings
from app.bot.balancer import balance_teams, Player
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard

import logging

logger = logging.getLogger(__name__)

router = Router()



@router.message(Command("create"))
async def cmd_create(message: types.Message):
    if message.chat.type != "private":
        try: await message.delete()
        except: pass
        return

    if message.from_user.id not in settings.admin_ids and message.from_user.id != settings.system_owner_id:
        return

    web_app_url = f"{settings.webapp_url}/web/index.html?v=10"
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="➕ Создать новую игру", web_app=types.WebAppInfo(url=web_app_url))]
    ])
    
    await message.answer(
        "Нажмите кнопку ниже, чтобы открыть форму создания игры.\n"
        "Вы сможете выбрать чат прямо внутри формы.",
        reply_markup=kb
    )

@router.message(Command("refresh_dashboard"))
async def cmd_refresh_dashboard(message: types.Message, session: AsyncSession):
    if message.from_user.id not in settings.admin_ids and message.from_user.id != settings.system_owner_id:
        return

    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer("⚠️ Использование: `/refresh_dashboard <game_id>`")
            return
            
        game_id = int(args[1])
        
        from app.bot.admin_dashboard import update_dashboard_message
        success = await update_dashboard_message(message.bot, game_id, session)
        
        if success:
            await message.answer("✅ Dashboard обновлен!")
        else:
            await message.answer("⚠️ Не удалось обновить. Проверьте ID игры и привязку админ-чата.")
            
    except ValueError:
        await message.answer("⚠️ ID игры должен быть числом.")
    except Exception as e:
        logger.error(f"Manual refresh error: {e}")
        await message.answer(f"❌ Ошибка: {e}")

# --- Merged from admin_tools.py ---

@router.callback_query(F.data.startswith("toggle_pay_"))
async def cb_toggle_pay(callback: types.CallbackQuery, session: AsyncSession):
    signup_id = int(callback.data.split("_")[2])
    signup = await session.get(Signup, signup_id)
    if not signup:
        await callback.answer("Запись не найдена")
        return
        
    signup.is_paid = not signup.is_paid
    await session.commit()
    await session.refresh(signup) # Force refresh for dashboard
    
    from app.bot.admin_dashboard import update_dashboard_message
    await update_dashboard_message(callback.bot, signup.game_id, session)
    await callback.answer("Статус оплаты изменен")

@router.callback_query(F.data.startswith("god_kick_menu_"))
async def cb_god_kick_menu(callback: types.CallbackQuery, session: AsyncSession):
    game_id = int(callback.data.split("_")[3])
    stmt = select(Signup, User).join(User).where(Signup.game_id == game_id).where(Signup.status == SignupStatus.ACTIVE).order_by(Signup.created_at)
    res = await session.execute(stmt)
    rows = res.all()
    
    if not rows:
        await callback.answer("Нет игроков для удаления")
        return
        
    buttons = []
    for signup, user in rows:
        name = user.full_name[:15]
        buttons.append([types.InlineKeyboardButton(text=f"❌ {name}", callback_data=f"kick_p_{signup.id}_{game_id}")])
    
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"god_dash_refresh_{game_id}")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text("🧨 <b>Выберите игрока для удаления:</b>", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("god_dash_refresh_"))
async def cb_god_dash_refresh(callback: types.CallbackQuery, session: AsyncSession):
    game_id = int(callback.data.split("_")[3])
    from app.bot.admin_dashboard import update_dashboard_message
    await update_dashboard_message(callback.bot, game_id, session, target_chat_id=callback.message.chat.id)

@router.callback_query(F.data.startswith("kick_p_"))
async def cb_kick_intent(callback: types.CallbackQuery):
    # Swap button with a confirmation button
    markup = callback.message.reply_markup
    # Data format: kick_p_{signup_id}_{game_id}
    parts = callback.data.split("_")
    signup_id = parts[2]
    game_id = parts[3]
    new_data = f"kick_c_{signup_id}_{game_id}"
    
    for row in markup.inline_keyboard:
        for btn in row:
            if btn.callback_data == callback.data:
                btn.text = "⚠️ ТОЧНО УДАЛИТЬ?"
                btn.callback_data = new_data
    
    try:
        await callback.message.edit_reply_markup(reply_markup=markup)
    except Exception: pass
    await callback.answer("Нажмите еще раз для удаления игрока")

@router.callback_query(F.data.startswith("kick_c_"))
async def cb_kick_confirm(callback: types.CallbackQuery, session: AsyncSession):
    # Format: kick_c_{signup_id}_{game_id}
    parts = callback.data.split("_")
    signup_id = int(parts[2])
    game_id = int(parts[3])
    
    signup = await session.get(Signup, signup_id)
    if not signup:
        await callback.answer("Запись не найдена")
        # Return to dashboard anyway
        from app.bot.admin_dashboard import update_dashboard_message
        await update_dashboard_message(callback.bot, game_id, session)
        return
        
    user_id = signup.user_id
    
    from app.services.game_service import GameService
    service = GameService(session)
    
    try:
        # We use is_admin=True to bypass the lock
        await service.leave_game(game_id, user_id, is_admin=True)
        
        # Success! return to kick menu to allow more kicks
        await callback.answer("Игрок удален")
        
        # Notify the user they were removed
        try:
            await callback.bot.send_message(user_id, f"⚠️ Администратор удалил вас из состава на игру #{game_id}.")
        except: pass
        
        # Return to kick menu
        await cb_god_kick_menu(callback, session)
        
    except Exception as e:
        await callback.answer(f"Ошибка: {e}")
        from app.bot.admin_dashboard import update_dashboard_message
        await update_dashboard_message(callback.bot, game_id, session)

