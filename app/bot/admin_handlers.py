from aiogram import Router, F, types
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Game, Signup, User, SignupStatus, GameStatus, Team, Chat, Position
from app.core.uow import UnitOfWork
from app.config import settings
from app.bot.utils import format_game_message, update_game_message
from app.bot.keyboards import get_game_keyboard, get_position_keyboard
from app.bot.fsm import GuestAddition
from aiogram.fsm.context import FSMContext
import time

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

    web_app_url = f"{settings.webapp_url.rstrip('/')}/web/index.html?v=1.3"
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="➕ Создать новую игру", web_app=types.WebAppInfo(url=web_app_url))]
    ])
    
    await message.answer(
        "Нажмите кнопку ниже, чтобы открыть форму создания игры.\n"
        "Вы сможете выбрать чат прямо внутри формы.",
        reply_markup=kb
    )


@router.message(Command("dashboard"))
async def cmd_dashboard(message: types.Message, session: AsyncSession):
    # System admins only for the command itself (or let the webapp handle auth, but hiding the button is better)
    if message.from_user.id not in settings.admin_ids and message.from_user.id != settings.system_owner_id:
        # Check if they are ChatAdmin in DB
        from app.db.models import ChatAdmin, User
        from sqlalchemy import select
        res = await session.execute(select(ChatAdmin).where(ChatAdmin.user_id == message.from_user.id))
        is_admin = res.first() is not None
        
        user_res = await session.execute(select(User).where(User.user_id == message.from_user.id))
        user = user_res.scalar_one_or_none()
        is_super = user and getattr(user, 'is_superadmin', False)
        
        if not (is_admin or is_super):
            return

    try:
        webapp_url = f"{settings.webapp_url.rstrip('/')}/web/admin.html"
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🛠 Открыть Dashboard", web_app=types.WebAppInfo(url=webapp_url))]
        ])
        
        await message.answer("Добро пожаловать в Admin Dashboard!\nНажмите кнопку ниже для управления вашими группами и играми.", reply_markup=kb)
    except Exception as e:
        logger.error(f"Dashboard Command Error: {e}")
        await message.answer(f"Ошибка вызова Dashboard: {e}")

@router.message(Command("force_refresh"))
async def cmd_force_refresh(message: types.Message, session: AsyncSession):
    if message.from_user.id not in settings.admin_ids and message.from_user.id != settings.system_owner_id:
        return

    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer("⚠️ Использование: `/force_refresh <game_id>`")
            return
            
        game_id = int(args[1])
        
        # 1. Reuse listener logic
        from app.bot.listeners import update_game_ui
        await update_game_ui(game_id)
        
        await message.answer("✅ Force refresh завершен.")

    except ValueError:
        await message.answer("⚠️ ID игры должен быть числом.")
    except Exception as e:
        logger.error(f"Force refresh error: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("start_voting"))
async def cmd_start_voting(message: types.Message, session: AsyncSession):
    if message.from_user.id not in settings.admin_ids and message.from_user.id != settings.system_owner_id:
        return

    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer("⚠️ Использование: `/start_voting <game_id>`")
            return
            
        game_id = int(args[1])
        
        from app.scheduler.tasks import send_voting_message
        await send_voting_message(game_id)
        
        await message.answer(f"✅ Голосование для игры #{game_id} отправлено!")
            
    except ValueError:
        await message.answer("⚠️ ID игры должен быть числом.")
    except Exception as e:
        logger.error(f"Manual voting trigger error: {e}")
        await message.answer(f"❌ Ошибка: {e}")




@router.message(Command("add_player"))
async def cmd_add_player(message: types.Message, session: AsyncSession):
    """
    Usage: /add_player <game_id> <user_id_or_username>
    """
    if message.from_user.id not in settings.admin_ids and message.from_user.id != settings.system_owner_id:
        return

    args = message.text.split()
    if len(args) != 3:
        await message.answer("⚠️ Использование: `/add_player <game_id> <id_или_@username>`")
        return

    try:
        game_id = int(args[1])
        user_input = args[2]
        
        target_user = None

        # 1. Try Lookup by ID
        if user_input.isdigit():
            target_user = await session.get(User, int(user_input))
        
        if not target_user:
            await message.answer(f"❌ Пользователь '{user_input}' не найден в базе данных бота.")
            return

        # 3. Add to Game via RosterService
        from app.core.services.roster import RosterService, SignupStatus
        
        async with UnitOfWork() as uow:
            service = RosterService(uow)
            result = await service.join_player(game_id, target_user, ignore_limit=True)
            
            if result.success:
                 await uow.commit()

        if result.success:
             await message.answer(f"✅ Игрок {target_user.full_name} успешно добавлен в игру #{game_id}! ({result.message})")
             try:
                 await message.bot.send_message(target_user.user_id, f"🎟️ Администратор добавил вас в игру #{game_id}.")

             except: pass
             
             # Publish Event
             from app.core.events import event_bus
             from app.core.services.roster import PlayerJoinedEvent
             
             if result.signup:
                 await event_bus.publish(PlayerJoinedEvent(
                     game_id=game_id, 
                     user_id=target_user.user_id, 
                     signup=result.signup, 
                     is_reserve=result.is_reserve, 
                     message=result.message
                ))

        else:
             await message.answer(f"⚠️ Не удалось добавить игрока: {result.message}")

    except Exception as e:
        logger.error(f"Add Player Error: {e}")
        await message.answer(f"❌ Ошибка: {e}")

# --- Guest Addition Flow ---

@router.message(GuestAddition.waiting_for_name)
async def process_guest_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("⚠️ Имя не может быть пустым. Введите имя гостя:")
        return
    
    await state.update_data(guest_name=name)
    await state.set_state(GuestAddition.waiting_for_position)
    
    from app.bot.keyboards import get_position_keyboard
    await message.answer(
        f"👤 Гость: <b>{name}</b>\n\nВыберите позицию игрока:",
        reply_markup=get_position_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(GuestAddition.waiting_for_position, F.data.startswith("pos_"))
async def process_guest_position(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    game_id = data.get("guest_game_id")
    name = data.get("guest_name")
    pos_str = callback.data.split("_")[1]
    
    if not game_id or not name:
        await callback.answer("❌ Ошибка данных. Попробуйте снова.")
        await state.clear()
        return

    guest_id = -int(time.time() * 1000)
    
    try:
        # Create Guest User
        new_guest = User(
            user_id=guest_id,
            full_name=f"{name} (Guest)",
            username=None,
            player_position=Position(pos_str),
            rating=100
        )
        session.add(new_guest)
        
        # Create Signup
        new_signup = Signup(
            game_id=game_id,
            user_id=guest_id,
            status=SignupStatus.RESERVE
        )
        session.add(new_signup)
        
        await session.commit()
        
        await callback.message.edit_text(f"✅ Гость <b>{name}</b> успешно добавлен в игру #{game_id}!", parse_mode="HTML")
        await state.clear()
        

        
        # Update Game UI if needed
        from app.bot.listeners import update_game_ui
        await update_game_ui(game_id)
        
    except Exception as e:
        logger.error(f"Bot Guest Addition Error: {e}")
        await session.rollback()
        await callback.message.answer(f"❌ Ошибка при добавлении гостя: {e}")
        await state.clear()

@router.callback_query(GuestAddition.waiting_for_position, F.data == "delete_msg")
async def cancel_guest_addition(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("Отменено")

@router.message(Command("promote"))
async def cmd_promote_admin(message: types.Message, session: AsyncSession):
    # Only superadmins can promote
    if message.from_user.id not in settings.admin_ids and message.from_user.id != settings.system_owner_id:
        return
        
    parts = message.text.split()
    if message.chat.type == "private":
        if len(parts) != 3:
            await message.answer("В личных сообщениях используйте: /promote <user_id> <chat_id>\nУзнать chat_id можно из логов или базы данных.")
            return
        chat_id = int(parts[2])
    else:
        if len(parts) != 2:
            await message.answer("В группе используйте: /promote <user_id>")
            return
        chat_id = message.chat.id
        
    try:
        target_uid = int(parts[1])
            
        from app.db.models import ChatAdmin
        from sqlalchemy import select
        
        res = await session.execute(select(ChatAdmin).where(ChatAdmin.user_id == target_uid, ChatAdmin.chat_id == chat_id))
        if res.first():
            await message.answer("Этот пользователь уже является администратором этой группы.")
            return
            
        ca = ChatAdmin(user_id=target_uid, chat_id=chat_id, can_edit_settings=True)
        session.add(ca)
        await session.commit()
        
        await message.answer(f"✅ Пользователь {target_uid} успешно назначен администратором группы {chat_id}!")
    except ValueError:
        await message.answer("user_id и chat_id должны быть числами.")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
