from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.fsm import Registration
from app.bot.keyboards import get_position_keyboard
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
    await state.update_data(full_name=message.text)
    await message.answer("Отлично! Теперь выберите вашу позицию:", reply_markup=get_position_keyboard())
    await state.set_state(Registration.waiting_for_position)

@router.callback_query(Registration.waiting_for_position, F.data.startswith("pos_"))
async def process_position(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    position_value = callback.data.split("_")[1]
    user_data = await state.get_data()
    full_name = user_data['full_name']
    
    # Save to DB
    new_user = User(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=full_name,
        position=Position(position_value)
    )
    session.add(new_user)
    await session.commit()
    
    await callback.message.edit_text(f"Регистрация успешна!\nИмя: {full_name}\nПозиция: {position_value}\n\nТеперь вы можете вернуться в чат и записаться на игру.")
    await state.clear()
