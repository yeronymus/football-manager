from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Position, User
from app.config import settings
from app.core.repositories.user_repository import UserRepository
from app.bot.fsm import EditingProfile
from app.bot.keyboards import (
    get_profile_edit_keyboard, 
    get_edit_choice_keyboard, 
    get_primary_select_keyboard, 
    get_multiselect_keyboard, 
    get_cancel_keyboard
)
import re

router = Router()

@router.message(Command("history"))
async def cmd_history(message: types.Message, _):
    current_chat_id = message.chat.id
    web_app_url = f"{settings.webapp_url.rstrip('/')}/web/history.html?chat_id={current_chat_id}&v=7"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text=_("btn_open_history"), 
            web_app=types.WebAppInfo(url=web_app_url)
        )]
    ])
    
    is_en = (_("btn_open_history") == "📜 Open Match History")
    prompt = "Click below to view group match history:" if is_en else "Нажмите кнопку ниже, чтобы посмотреть архив игр текущей группы:"
    await message.answer(prompt, reply_markup=kb)

@router.message(F.text.in_(["👤 Мой профиль", "👤 My Profile"]))
@router.message(Command("my_profile"))
@router.message(Command("profile"))
async def cmd_my_profile(message: types.Message, _):
    if message.chat.type != "private":
        try:
            await message.delete()
        except:
            pass
        return

    from app.config import settings
    base = settings.webapp_url.rstrip("/")
    web_app_url = f"{base}/web/profile.html?v=7"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text=_("btn_open_profile"), 
            web_app=types.WebAppInfo(url=web_app_url)
        )]
    ])
    
    is_en = (_("btn_open_profile") == "👤 Open Profile")
    prompt = "Click below to open your profile:" if is_en else "Нажмите кнопку ниже, чтобы открыть ваш профиль:"
    await message.answer(prompt, reply_markup=kb)

async def render_profile(messageable: types.Message, user_id: int, session: AsyncSession, player=None):
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    
    lang = "en"
    if user and user.language:
        lang = user.language.value if hasattr(user.language, "value") else str(user.language)
    elif hasattr(messageable, "from_user") and messageable.from_user and messageable.from_user.language_code and messageable.from_user.language_code.startswith("ru"):
        lang = "ru"
    lang = (lang or "en").lower()
    is_en = (lang == "en")

    if not user:
        not_reg = "You are not registered yet. Press /start to begin!" if is_en else "Вы еще не зарегистрированы. Нажмите /start"
        if isinstance(messageable, types.Message):
            await messageable.answer(not_reg)
        elif isinstance(messageable, types.CallbackQuery):
             await messageable.answer(not_reg)
        return

    # Calculate total goals
    stats = await user_repo.get_user_stats(user_id)
    total_goals = stats.get("goals", 0)

    # Legacy baseline migration: convert legacy rating (1200) to current baseline (100)
    if player and player.rating == 1200:
        player.rating = 100
        await session.commit()
        
    if user and user.rating == 1200:
        user.rating = 100
        await session.commit()

    if is_en:
        text = f"👤 <b>Player Profile</b>\n\n"
        text += f"<b>{user.full_name}</b> (@{user.username or 'none'})\n"
        text += f"📍 Position: <b>{user.player_position.value}</b>\n"
        if user.alt_positions:
            text += f"🔄 Alt positions: {', '.join(user.alt_positions)}\n"
        text += f"➖➖➖➖➖➖➖➖\n"
        rating_val = player.rating if player else "(See in group chat)"
        text += f"📊 Rating: <b>{rating_val}</b>\n"
        text += f"🎮 Matches: <b>{player.games_played if player else '-'}</b>\n"
        text += f"⭐️ MVP: <b>{player.stats_mvp if player else '-'}</b>\n"
        text += f"⚽ Goals: <b>{total_goals}</b>"
    else:
        text = f"👤 <b>Профиль игрока</b>\n\n"
        text += f"<b>{user.full_name}</b> (@{user.username or 'нет'})\n"
        text += f"📍 Позиция: <b>{user.player_position.value}</b>\n"
        if user.alt_positions:
            text += f"🔄 Доп. позиции: {', '.join(user.alt_positions)}\n"
        text += f"➖➖➖➖➖➖➖➖\n"
        rating_val = player.rating if player else "(Смотрите в группе)"
        text += f"📊 Рейтинг: <b>{rating_val}</b>\n"
        text += f"🎮 Матчей: <b>{player.games_played if player else '-'}</b>\n"
        text += f"⭐️ MVP: <b>{player.stats_mvp if player else '-'}</b>\n"
        text += f"⚽ Голов: <b>{total_goals}</b>"

    kb = get_profile_edit_keyboard(lang=lang)
    try:
        if messageable.from_user.is_bot:
            await messageable.edit_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await messageable.answer(text, reply_markup=kb, parse_mode="HTML")
    except:
        await messageable.answer(text, reply_markup=kb, parse_mode="HTML")

@router.message(F.text.in_(["📜 Мои матчи", "📜 My Matches"]))
@router.message(Command("my_history"))
async def cmd_my_history(message: types.Message, _):
    if message.chat.type != "private":
        try:
            await message.delete()
        except:
            pass
        return

    from app.config import settings
    base = settings.webapp_url.rstrip("/")
    web_app_url = f"{base}/web/history.html?v=7"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text=_("btn_open_history"), 
            web_app=types.WebAppInfo(url=web_app_url)
        )]
    ])
    
    is_en = (_("btn_open_history") == "📜 Open Match History")
    prompt = "Click below to view your match history:" if is_en else "Нажмите кнопку ниже, чтобы посмотреть архив игр:"
    await message.answer(prompt, reply_markup=kb)

# --- Profile Editing Handlers ---

@router.callback_query(F.data == "edit_profile")
async def cb_edit_profile(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.get_user(callback.from_user.id)
    lang = user.language.value if (user and user.language) else "en"
    
    await callback.message.edit_reply_markup(reply_markup=get_edit_choice_keyboard(lang=lang))
    await state.set_state(EditingProfile.waiting_for_choice)

@router.callback_query(F.data == "edit_cancel")
async def cb_edit_cancel(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    await callback.answer()
    await render_profile(callback.message, callback.from_user.id, session)

@router.callback_query(F.data == "back_to_edit_menu")
async def cb_back_to_edit_menu(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.get_user(callback.from_user.id)
    lang = user.language.value if (user and user.language) else "en"
    is_en = (lang == "en")
    
    prompt = "Select what you want to change:" if is_en else "Выберите, что хотите изменить:"
    await callback.message.edit_text(prompt, reply_markup=get_edit_choice_keyboard(lang=lang))
    await state.set_state(EditingProfile.waiting_for_choice)
    await callback.answer()

@router.callback_query(F.data == "edit_name")
async def cb_edit_name(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.get_user(callback.from_user.id)
    lang = user.language.value if (user and user.language) else "en"
    is_en = (lang == "en")
    
    prompt = "Enter your new First and Last name (Latin letters only):" if is_en else "Введите ваше новое Имя и Фамилию (только латиница):"
    await callback.message.edit_text(prompt, reply_markup=get_cancel_keyboard(lang=lang))
    await state.set_state(EditingProfile.waiting_for_name)
    await callback.answer()

@router.message(EditingProfile.waiting_for_name)
async def process_edit_name_input(message: types.Message, state: FSMContext, session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.get_user(message.from_user.id)
    lang = user.language.value if (user and user.language) else "en"
    is_en = (lang == "en")

    # Validation
    if not re.match(r"^[a-zA-Z\s]+$", message.text):
        err = "Please use Latin letters only.\nTry again:" if is_en else "Пожалуйста, используйте только латинские буквы.\nПопробуйте еще раз:"
        await message.answer(err)
        return
        
    try: await message.delete()
    except: pass
    
    user = await user_repo.update_profile(message.from_user.id, full_name=message.text)
    await session.commit()
    
    success = f"✅ Name updated to: {user.full_name}" if is_en else f"✅ Имя обновлено на: {user.full_name}"
    await message.answer(success)
    
    await state.clear()
    await render_profile(message, message.from_user.id, session)

@router.callback_query(F.data == "edit_position")
async def cb_edit_position(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.get_user(callback.from_user.id)
    lang = user.language.value if (user and user.language) else "en"
    is_en = (lang == "en")

    all_positions = [p.value for p in Position]
    prompt = "Select your new primary position:" if is_en else "Выберите новую позицию:"
    await callback.message.edit_text(prompt, reply_markup=get_primary_select_keyboard(all_positions))
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
        
    is_en = (str(user.language or "en").lower() == "en")
    toast = f"✅ Position updated to: {full_pos}" if is_en else f"✅ Позиция обновлена на: {full_pos}"
    await callback.answer(toast, show_alert=False)
    
    await state.clear()
    await render_profile(callback.message, callback.from_user.id, session)
    
@router.callback_query(F.data == "edit_alt_positions")
async def cb_edit_alt_positions(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.get_user(callback.from_user.id)
    if not user:
        return
    
    current_alts = user.alt_positions or []
    current_alts = [str(p) for p in current_alts]
    
    is_en = (str(user.language or "en").lower() == "en")
    prompt = "Select your alternative positions (Toggle):" if is_en else "Выберите ваши дополнительные позиции (Toggle):"

    await state.update_data(alt_positions=current_alts)
    await callback.message.edit_text(
        prompt,
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
    
    user_repo = UserRepository(session)
    user = await user_repo.get_user(callback.from_user.id)
    is_en = (str(user.language or "en").lower() == "en") if user else True

    if not selected:
        warn = "Select at least one position or click Back." if is_en else "Выберите хотя бы одну или нажмите Отмена в меню, если передумали."
        await callback.answer(warn, show_alert=True)
        return

    user = await user_repo.update_profile(callback.from_user.id, alt_positions=selected)
    await session.commit()
    
    toast = f"✅ Alt positions updated: {', '.join(selected)}" if is_en else f"✅ Доп. позиции обновлены: {', '.join(selected)}"
    await callback.answer(toast, show_alert=False)
    await state.clear()
    await render_profile(callback.message, callback.from_user.id, session)
