from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.models import User, Position, Game, Signup, SignupStatus, GameStats, GameStatus, RatingHistory, Team
from app.config import settings
from app.services.user_service import UserService
from app.bot.fsm import EditingProfile
from app.bot.keyboards import get_profile_edit_keyboard, get_edit_choice_keyboard, get_primary_select_keyboard, get_multiselect_keyboard, get_cancel_keyboard
import re

router = Router()

@router.message(Command("history"))
async def cmd_history(message: types.Message):
    # Мы берем ID текущего чата, где написали команду
    current_chat_id = message.chat.id
    
    # Формируем URL с параметром
    web_app_url = f"{settings.webapp_url}/web/history.html?chat_id={current_chat_id}"
    
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
async def cmd_my_profile(message: types.Message, session: AsyncSession):
    if message.chat.type != "private":
        return
    await render_profile(message, message.from_user.id, session)

async def render_profile(messageable: types.Message, user_id: int, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_user(user_id)
    
    if not user:
        if isinstance(messageable, types.Message):
            await messageable.answer("Вы еще не зарегистрированы. Нажмите /start")
        elif isinstance(messageable, types.CallbackQuery): # Should not happen if passed message
             await messageable.answer("Вы еще не зарегистрированы.")
        return

    # Calculate total goals
    stats = await user_service.get_user_stats(user_id)
    total_goals = stats.get("goals", 0)

    text = f"👤 <b>Профиль игрока</b>\n\n"
    text += f"<b>{user.full_name}</b> (@{user.username or 'нет'})\n"
    text += f"📍 Позиция: <b>{user.player_position.value}</b>\n"
    
    if user.alt_positions:
        text += f"🔄 Доп. позиции: {', '.join(user.alt_positions)}\n"
        
    text += f"➖➖➖➖➖➖➖➖\n"
    
    # Always show rating (User request)
    # FIX: Check for legacy default rating (1200) and fix to new default (100)
    if user.rating == 1200:
        user.rating = 100
        await session.commit()
        
    text += f"📊 Рейтинг: <b>{user.rating}</b>\n"
    
    text += f"🎮 Матчей: <b>{user.games_played}</b>\n"
    text += f"⭐️ MVP: <b>{user.stats_mvp}</b>\n"
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
async def cmd_my_history(message: types.Message, session: AsyncSession):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id

    # 1. Запрашиваем последние 10 игр, в которых участвовал юзер
    query = (
        select(Game, Signup, GameStats, RatingHistory)
        .join(Signup, Game.id == Signup.game_id)
        .outerjoin(GameStats, (Game.id == GameStats.game_id) & (GameStats.user_id == user_id))
        .outerjoin(RatingHistory, (Game.id == RatingHistory.game_id) & (RatingHistory.user_id == user_id))
        .where(
            Signup.user_id == user_id,
            Signup.status == SignupStatus.ACTIVE,
            Game.status == GameStatus.FINISHED
        )
        .order_by(desc(Game.date_time))
        .limit(10)
    )

    result = await session.execute(query)
    matches = result.all()

    if not matches:
        await message.answer("Вы еще не сыграли ни одного матча.")
        return

    # 2. Формируем красивый текст
    text = "<b>📜 Ваши последние игры:</b>\n\n"

    for game, signup, stats, rating in matches:
        # А. Определяем результат и иконку команды
        team_icon = "⚪"
        if signup.team == Team.A: team_icon = "🟠"
        elif signup.team == Team.B: team_icon = "🟢"
        elif signup.team == Team.C: team_icon = "🔵"

        result_icon = "🤝" 
        if game.winner_team:
            if game.winner_team == signup.team:
                result_icon = "🏆" # Победа
            else:
                result_icon = "❌" # Поражение
        
        # Б. Счет матча
        score_text = f"{game.score_a or 0}:{game.score_b or 0}"
        if game.team_count == 3:
            score_text += f":{game.score_c or 0}"
        
        # В. Строка матча
        date_str = game.date_time.strftime("%d.%m")
        # Извлекаем краткое название локации (первая часть до запятой или палки)
        loc_short = game.location.split('|')[0].split(',')[0].strip()
        
        text += f"{result_icon} <b>{date_str} | {loc_short}</b> ({score_text})\n"
        
        # Г. Личная статистика (Детали)
        details = []
        details.append(f"{team_icon} Команда")

        # Голы
        if stats and stats.goals > 0:
            details.append(f"⚽ {stats.goals} гол")
            
        # Рейтинг (MMR change)
        if rating:
            sign = "+" if rating.change > 0 else ""
            details.append(f"{sign}{rating.change} MMR")
        
        text += f"   └ <i>{ ' • '.join(details) }</i>\n\n"

    # Добавляем общую стату в подвал
    user = await session.get(User, user_id)
    text += f"➖➖➖➖➖➖➖➖\n"
    text += f"👤 <b>{user.full_name}</b>\n"
    text += f"📊 Рейтинг: <b>{user.rating}</b>\n"
    text += f"🎮 Матчей: <b>{user.games_played}</b>"

    await message.answer(text)

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
    
    user_service = UserService(session)
    user = await user_service.update_profile(message.from_user.id, full_name=message.text)
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
    
    user_service = UserService(session)
    user = await user_service.update_profile(callback.from_user.id, position=Position(position_value))
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
    user_service = UserService(session)
    user = await user_service.get_user(callback.from_user.id)
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

    user_service = UserService(session)
    user = await user_service.update_profile(callback.from_user.id, alt_positions=selected)
    await session.commit()
    
    await callback.answer(f"✅ Доп. позиции обновлены: {', '.join(selected)}", show_alert=False)
    await state.clear()
    await render_profile(callback.message, callback.from_user.id, session)
