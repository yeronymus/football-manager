from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Game
from app.core.repositories.user_repository import UserRepository
from app.bot.fsm import Registration
from app.bot.keyboards import get_multiselect_keyboard, get_primary_select_keyboard, get_game_keyboard
import re

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")

@router.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    # Validation: Latin letters only
    if not re.match(r"^[a-zA-Z\s]+$", message.text):
        await message.answer("Пожалуйста, используйте только латинские буквы (Latin letters only).\nПопробуйте еще раз:")
        return

    await state.update_data(full_name=message.text, alt_positions=[])
    await message.answer("Отлично! Выберите ВСЕ позиции, на которых вы можете играть (нажимайте, чтобы выбрать):", reply_markup=get_multiselect_keyboard([]))
    await state.set_state(Registration.waiting_for_alt_positions)

@router.callback_query(Registration.waiting_for_alt_positions, F.data.startswith("toggle_"))
async def process_alt_position_toggle(callback: types.CallbackQuery, state: FSMContext):
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

@router.callback_query(Registration.waiting_for_alt_positions, F.data == "done_alt_pos")
async def process_alt_position_done(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("alt_positions", [])
    
    if not selected:
        await callback.answer("Выберите хотя бы одну позицию!", show_alert=True)
        return
    
    await callback.message.edit_text("Теперь выберите вашу ОСНОВНУЮ позицию (для балансировки):", reply_markup=get_primary_select_keyboard(selected))
    await state.set_state(Registration.waiting_for_position)

@router.callback_query(Registration.waiting_for_position, F.data.startswith("primary_"))
async def process_position(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    position_value = callback.data.split("_")[1]
    user_data = await state.get_data()
    full_name = user_data['full_name']
    alt_positions = user_data.get('alt_positions', [])
    pending_game_id = user_data.get('pending_game_id')
    
    if position_value in alt_positions:
        alt_positions.remove(position_value)
    
    if position_value in alt_positions:
        alt_positions.remove(position_value)
    
    # Save to DB via Repository
    user_repo = UserRepository(session)
    new_user = await user_repo.create_user(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=full_name,
        position=position_value,
        alt_positions=alt_positions
    )
    await session.commit()
    
    full_pos_str = position_value
    if alt_positions:
        full_pos_str += f" ({', '.join(alt_positions)})"
    
    await callback.message.edit_text(f"Регистрация успешна! ✅\n\n👤 {full_name}\n📍 {full_pos_str}")
    await state.clear()
    
    # Redirect to pending game if any
    if pending_game_id:
        result = await session.execute(select(Game).where(Game.id == pending_game_id))
        game = result.scalar_one_or_none()
        if game:
            from app.bot.utils import format_game_message
            text = await format_game_message(game, session)
            await callback.message.answer(text, reply_markup=get_game_keyboard(pending_game_id))
            
            # TRIGGER DASHBOARD UPDATE
            from app.bot.admin_dashboard import update_dashboard_message
            await update_dashboard_message(callback.bot, game.id, session)
        else:
            await callback.message.answer("Игра, которую вы искали, не найдена, но вы теперь зарегистрированы!")
