from aiogram import Router, F, types
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_session
from app.db.models import Game, Signup, User, SignupStatus, GameStatus
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard
import logging

router = Router()

@router.callback_query(F.data.startswith("join_"))
async def process_join(callback: types.CallbackQuery, session: AsyncSession):
    game_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # Check if user is registered
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Сначала зарегистрируйтесь! (Нажмите /start в ЛС)", show_alert=True, url=f"https://t.me/{callback.bot.username}?start=reg")
        return

    # Lock the game row for update to handle race conditions
    # This ensures only one transaction can check count and insert at a time for this game
    result = await session.execute(
        select(Game).where(Game.id == game_id).with_for_update()
    )
    game = result.scalar_one_or_none()
    
    if not game or game.status != GameStatus.OPEN:
        await callback.answer("Запись закрыта!")
        return

    # Check if already signed up (after lock to be sure)
    result = await session.execute(select(Signup).where(Signup.game_id == game_id, Signup.user_id == user_id))
    existing_signup = result.scalar_one_or_none()
    
    if existing_signup:
        await callback.answer("Вы уже записаны!")
        return

    # Count current active signups
    result = await session.execute(select(func.count(Signup.id)).where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE))
    active_count = result.scalar()
    
    status = SignupStatus.ACTIVE if active_count < game.max_players else SignupStatus.RESERVE
    
    new_signup = Signup(game_id=game_id, user_id=user_id, status=status)
    session.add(new_signup)
    
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        await callback.answer("Ошибка записи. Попробуйте снова.")
        return

    # Update message
    text = await format_game_message(game, session)
    try:
        await callback.message.edit_text(text, reply_markup=get_game_keyboard(game_id))
    except Exception:
        pass # Message not modified

    await callback.answer("Вы записаны!" if status == SignupStatus.ACTIVE else "Вы в резерве!")

@router.callback_query(F.data.startswith("leave_"))
async def process_leave(callback: types.CallbackQuery, session: AsyncSession):
    game_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # Check if signed up
    result = await session.execute(select(Signup).where(Signup.game_id == game_id, Signup.user_id == user_id))
    signup = result.scalar_one_or_none()
    
    if not signup:
        await callback.answer("Вы не записаны!")
        return
        
    was_active = signup.status == SignupStatus.ACTIVE
    await session.delete(signup)
    
    # Auto-promotion logic
    game_result = await session.execute(select(Game).where(Game.id == game_id))
    game = game_result.scalar_one_or_none()

    if was_active and game.status == GameStatus.OPEN:
        # Promote first reserve
        reserve_result = await session.execute(
            select(Signup)
            .where(Signup.game_id == game_id, Signup.status == SignupStatus.RESERVE)
            .order_by(Signup.created_at)
            .limit(1)
        )
        first_reserve = reserve_result.scalar_one_or_none()
        
        if first_reserve:
            first_reserve.status = SignupStatus.ACTIVE
            # Notify user (optional, requires bot to initiate chat)
            try:
                await callback.bot.send_message(first_reserve.user_id, f"Вы переведены в основной состав на игру {game.location}!")
            except:
                pass

    await session.commit()
    
    # Update message
    text = await format_game_message(game, session)
    try:
        await callback.message.edit_text(text, reply_markup=get_game_keyboard(game_id))
    except Exception:
        pass

    await callback.answer("Вы выписались.")
