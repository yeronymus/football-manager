from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.fsm import Registration
from app.bot.fsm import Registration
from app.bot.keyboards import get_multiselect_keyboard, get_primary_select_keyboard
from app.db.database import get_session
from app.db.models import User, Position

router = Router()

@router.message(CommandStart(deep_link=True))
async def cmd_start_deep_link(message: types.Message, command: CommandObject, state: FSMContext, session: AsyncSession):
    """
    Handle deep linking for registration (e.g., t.me/bot?start=reg)
    """
    args = command.args
    if args == "reg":
        # Check if user already exists
        result = await session.execute(select(User).where(User.user_id == message.from_user.id))
        user = result.scalar_one_or_none()
        
        if user:
            await message.answer("Вы уже зарегистрированы!")
            return

        await message.answer("Добро пожаловать! Как вас зовут? (Введите Имя Фамилия)")
        await state.set_state(Registration.waiting_for_name)
    else:
        await message.answer("Неизвестная команда.")

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я футбольный менеджер. Используйте кнопки в чате для записи на игру.")

@router.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
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
    
    # Remove primary from alt_positions to avoid redundancy? 
    # Or keep it? The prompt says "Main role + Alt roles". 
    # Usually "Alt" implies "Other than Main".
    if position_value in alt_positions:
        alt_positions.remove(position_value)
    
    # Save to DB
    new_user = User(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=full_name,
        position=Position(position_value),
        alt_positions=alt_positions
    )
    session.add(new_user)
    await session.commit()
    
    await callback.message.edit_text(f"Регистрация успешна!\nИмя: {full_name}\nОсновная: {position_value}\nДоп.: {', '.join(alt_positions)}\n\nТеперь вы можете вернуться в чат и записаться на игру.")
    await state.clear()
