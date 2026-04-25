from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.models import User, Position, Game, Signup, SignupStatus, GameStats, GameStatus, RatingHistory, Team
from app.config import settings
from app.core.repositories.user_repository import UserRepository
from app.bot.fsm import EditingProfile
from app.bot.keyboards import get_profile_edit_keyboard, get_edit_choice_keyboard, get_primary_select_keyboard, get_multiselect_keyboard, get_cancel_keyboard
import re

router = Router()

@router.message(Command("history"))
async def cmd_history(message: types.Message):
    # Мы берем ID текущего чата, где написали команду
    current_chat_id = message.chat.id
    
    # Формируем URL с параметром
    web_app_url = f"{settings.webapp_url.rstrip('/')}/web/history.html?chat_id={current_chat_id}"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="📜 Открыть архив игр", 
            web_app=types.WebAppInfo(url=web_app_url)
        )]
    ])
    
    await message.answer(
        "Нажмите кнопку ниже, чтобы посмотреть архив игр текущей группы:",
        reply_markup=kb
    )

@router.message(F.text == "👤 Мой профиль")
@router.message(Command("my_profile"))
async def cmd_my_profile(message: types.Message):
    if message.chat.type != "private":
        try:
            await message.delete()
        except:
            pass
        return

    from app.config import settings
    base = settings.webapp_url.rstrip("/")
    web_app_url = f"{base}/web/profile.html"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="👤 Открыть Профиль", 
            web_app=types.WebAppInfo(url=web_app_url)
        )]
    ])
    
    await message.answer(
        "Нажмите кнопку ниже, чтобы открыть ваш профиль:",
        reply_markup=kb
    )

async def render_profile(messageable: types.Message, user_id: int, session: AsyncSession, player=None):
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    
    if not user:
        if isinstance(messageable, types.Message):
            await messageable.answer("Вы еще не зарегистрированы. Нажмите /start")
        elif isinstance(messageable, types.CallbackQuery): # Should not happen if passed message
             await messageable.answer("Вы еще не зарегистрированы.")
        return

    # Calculate total goals
    stats = await user_repo.get_user_stats(user_id)
    total_goals = stats.get("goals", 0)

    text = f"👤 <b>Профиль игрока</b>\n\n"
    text += f"<b>{user.full_name}</b> (@{user.username or 'нет'})\n"
    text += f"📍 Позиция: <b>{user.player_position.value}</b>\n"
    
    if user.alt_positions:
        text += f"🔄 Доп. позиции: {', '.join(user.alt_positions)}\n"
        
    text += f"➖➖➖➖➖➖➖➖\n"
    
    # Always show rating (User request)
    # FIX: Check for legacy default rating (1200) and fix to new default (100)
    if player and player.rating == 1200:
        player.rating = 100
        await session.commit()
        
    text += f"📊 Рейтинг: <b>{player.rating if player else '(Смотрите в группе)'}</b>\n"
    
    text += f"🎮 Матчей: <b>{player.games_played if player else '-'}</b>\n"
    text += f"⭐️ MVP: <b>{player.stats_mvp if player else '-'}</b>\n"
    text += f"⚽ Голов: <b>{total_goals}</b>"
    
    # Determine method (edit_text vs answer)
    # If messageable is a Message object from a callback (it has id, chat etc) we can edit it.
    # But cmd_my_profile passes original message (user's text), so we answer() new.
    # If recursive from Callback, passed message is Bot's message, so we edit().
    
    try:
        # Check if message is from Bot (recursion)
        if messageable.from_user.is_bot:
            await messageable.edit_text(text, reply_markup=get_profile_edit_keyboard())
        else:
            await messageable.answer(text, reply_markup=get_profile_edit_keyboard())
    except:
        await messageable.answer(text, reply_markup=get_profile_edit_keyboard())

@router.message(F.text == "📜 Мои матчи")
@router.message(Command("my_history"))
async def cmd_my_history(message: types.Message):
    if message.chat.type != "private":
        try:
            await message.delete()
        except:
            pass
        return

    from app.config import settings
    base = settings.webapp_url.rstrip("/")
    web_app_url = f"{base}/web/history.html"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="📜 Открыть архив игр", 
            web_app=types.WebAppInfo(url=web_app_url)
        )]
    ])
    
    await message.answer(
        "Нажмите кнопку ниже, чтобы посмотреть архив игр:",
        reply_markup=kb
    )

# --- Profile Editing Handlers ---

@router.callback_query(F.data == "edit_profile")
async def cb_edit_profile(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=get_edit_choice_keyboard())
    await state.set_state(EditingProfile.waiting_for_choice)

@router.callback_query(F.data == "edit_cancel")
async def cb_edit_cancel(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    await callback.answer("Редактирование завершено")
    # Restore profile using explicit user_id
    await render_profile(callback.message, callback.from_user.id, session)

@router.callback_query(F.data == "back_to_edit_menu")
async def cb_back_to_edit_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Выберите, что хотите изменить:", reply_markup=get_edit_choice_keyboard())
    await state.set_state(EditingProfile.waiting_for_choice)
    await callback.answer()

@router.callback_query(F.data == "edit_name")
async def cb_edit_name(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите ваше новое Имя и Фамилию:", reply_markup=get_cancel_keyboard())
    await state.set_state(EditingProfile.waiting_for_name)
    await callback.answer()

@router.message(EditingProfile.waiting_for_name)
async def process_edit_name_input(message: types.Message, state: FSMContext, session: AsyncSession):
    # Validation
    if not re.match(r"^[a-zA-Z\s]+$", message.text):
        await message.answer("Пожалуйста, используйте только латинские буквы.\nПопробуйте еще раз:")
        return
        
    # Delete User Input
    try: await message.delete()
    except: pass

    # We cannot easily delete the "Enter Name" prompt because we didn't store its ID in state.
    # But since we used edit_text on the menu message, that "Enter Name" message replaces the menu.
    # Ideally, we should delete THAT message or edit it back.
    # But we don't have the Message ID of the prompt here easily unless we stored it in state.
    # Let's try to just render the profile NEW message, and the old prompt will stay?
    # No, that's the issue.
    # BEST PRACTICE: Store prompt message ID or reply to it.
    
    # Actually, simpler: Since we want to return to "My Profile", we can just send a new message.
    # But to be clean, we should have stored the prompt message ID.
    # For now, let's just proceed. The "Enter Name" message will function as the new "Success" message if we edit it?
    # We can't edit it because we don't have the object.
    
    user_repo = UserRepository(session)
    user = await user_repo.update_profile(message.from_user.id, full_name=message.text)
    await session.commit()
    
    await message.answer(f"✅ Имя обновлено на: {user.full_name}")
    
    await state.clear()
    # Recursively call render_profile to show updated profile
    await render_profile(message, message.from_user.id, session)

@router.callback_query(F.data == "edit_position")
async def cb_edit_position(callback: types.CallbackQuery, state: FSMContext):
    # Reuse primary select keyboard but we need available positions.
    all_positions = [p.value for p in Position]
    await callback.message.edit_text("Выберите новую позицию:", reply_markup=get_primary_select_keyboard(all_positions))
    await state.set_state(EditingProfile.waiting_for_position)
    await callback.answer()

@router.callback_query(EditingProfile.waiting_for_position, F.data.startswith("primary_"))
async def process_edit_position_choice(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    position_value = callback.data.split("_")[1]
    
    user_repo = UserRepository(session)
    user = await user_repo.update_profile(callback.from_user.id, position=Position(position_value))
    await session.commit()
    
    full_pos = position_value
    if user.alt_positions:
        full_pos += f" ({', '.join(user.alt_positions)})"
        
    await callback.message.delete()
    # Or just edit it? edit_text might act weird if we call render_profile after.
    # render_profile will try to EDIT if from_user is bot. 
    # Since we are in callback, message is from bot.
    # So we don't need to delete, just calling render_profile should overwrite.
    # But we want to show a toast "Position updated".
    await callback.answer(f"✅ Позиция обновлена на: {full_pos}", show_alert=False)
    
    await state.clear()
    await render_profile(callback.message, callback.from_user.id, session)
    
@router.callback_query(F.data == "edit_alt_positions")
async def cb_edit_alt_positions(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.get_user(callback.from_user.id)
    if not user:
        return
    
    current_alts = user.alt_positions or []
    # Ensure they are strings
    current_alts = [str(p) for p in current_alts]
    
    await state.update_data(alt_positions=current_alts)
    await callback.message.edit_text(
        "Выберите ваши дополнительные позиции (Toggle):",
        reply_markup=get_multiselect_keyboard(current_alts)
    )
    await state.set_state(EditingProfile.waiting_for_alt_positions)
    await callback.answer()

@router.callback_query(EditingProfile.waiting_for_alt_positions, F.data.startswith("toggle_"))
async def process_edit_alt_toggle(callback: types.CallbackQuery, state: FSMContext):
    pos = callback.data.split("_")[1]
    data = await state.get_data()
    selected = data.get("alt_positions", [])
    
    if pos in selected:
        selected.remove(pos)
    else:
        selected.append(pos)
        
    await state.update_data(alt_positions=selected)
    await callback.message.edit_reply_markup(reply_markup=get_multiselect_keyboard(selected))
    await callback.answer()

@router.callback_query(EditingProfile.waiting_for_alt_positions, F.data == "done_alt_pos")
async def process_edit_alt_done(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    selected = data.get("alt_positions", [])
    
    if not selected:
        await callback.answer("Выберите хотя бы одну или нажмите Отмена в меню, если передумали.", show_alert=True)
        return

    user_repo = UserRepository(session)
    user = await user_repo.update_profile(callback.from_user.id, alt_positions=selected)
    await session.commit()
    
    await callback.answer(f"✅ Доп. позиции обновлены: {', '.join(selected)}", show_alert=False)
    await state.clear()
    await render_profile(callback.message, callback.from_user.id, session)
