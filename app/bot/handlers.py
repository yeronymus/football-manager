from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.fsm import Registration
from app.bot.keyboards import get_multiselect_keyboard, get_primary_select_keyboard, get_main_menu_keyboard
from app.db.database import get_session
from app.db.models import User, Position, Game, Signup, GameStats, RatingHistory, SignupStatus, GameStatus, Team
from app.config import settings

from aiogram.filters import CommandStart, CommandObject, Command, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated
from app.db.models import Chat

router = Router()

from app.bot.keyboards import get_game_keyboard
import re

@router.message(F.is_automatic_forward == True)
async def handle_auto_forward(message: types.Message):
    # Ignore if somehow triggered by bot itself (though auto_forward usually implies channel->group)
    if message.from_user and message.from_user.is_bot:
        return
    # Detect if it's a game message (look for hidden link or specific text)
    # The hidden link is: <a href="https://t.me/fm_metabot?start=game_{id}">
    
    # Extract entities
    if not message.entities:
        return

    game_id = None
    for entity in message.entities:
        if entity.type == "text_link" and entity.url:
            match = re.search(r"start=game_(\d+)", entity.url)
            if match:
                game_id = int(match.group(1))
                break
    
    if game_id:
        await message.reply(
            "ㅤ", # Invisible character U+3164
            reply_markup=get_game_keyboard(game_id)
        )

# Listen for bot being added to a group or promoted
@router.my_chat_member(F.new_chat_member.status.in_({"member", "administrator", "creator"}))
async def on_chat_member_update(event: ChatMemberUpdated, session: AsyncSession):
    # Save chat to DB if bot is added
    chat = await session.get(Chat, event.chat.id)
    if not chat:
        chat = Chat(chat_id=event.chat.id, title=event.chat.title or "Unknown Chat")
        session.add(chat)
        await session.commit()

@router.message(Command("register_chat"))
@router.channel_post(Command("register_chat"))
async def cmd_register_chat(message: types.Message, session: AsyncSession):
    if message.is_automatic_forward:
        return

    # В каналах message.from_user может быть None.
    # Если это канал, мы считаем, что писать от имени канала может только админ.
    # Если это группа, проверяем ID юзера.
    if message.chat.type in ["group", "supergroup"]:
        if message.from_user.id not in settings.ADMIN_IDS:
            return 
    elif message.chat.type == "channel":
        # В канале просто доверяем, так как постит админ
        pass
    else:
        await message.answer("Эту команду нужно использовать в группе или канале.")
        return

    chat = await session.get(Chat, message.chat.id)
    if not chat:
        chat = Chat(chat_id=message.chat.id, title=message.chat.title or "Unknown Chat")
        session.add(chat)
        await session.commit()
        await message.answer("✅ Чат успешно зарегистрирован! Теперь он появится в списке при создании игры.")
    else:
        await message.answer("✅ Чат уже зарегистрирован.")

@router.message(Command("chats"))
async def cmd_list_chats(message: types.Message, session: AsyncSession):
    if message.from_user.id not in settings.ADMIN_IDS:
        return

    result = await session.execute(select(Chat))
    chats = result.scalars().all()

    if not chats:
        await message.answer("Нет зарегистрированных чатов.")
        return

    text = "📢 **Зарегистрированные чаты:**\n\n"
    for chat in chats:
        text += f"▪️ <b>{chat.title}</b> (ID: <code>{chat.chat_id}</code>)\n"

    await message.answer(text)

from app.bot.utils import format_game_message

@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject, state: FSMContext, session: AsyncSession):
    """
    Unified /start handler.
    Matches both /start and /start <args> (deep links).
    """
    args = command.args
    
    # 1. Check User Existence
    result = await session.execute(select(User).where(User.user_id == message.from_user.id))
    user = result.scalar_one_or_none()

    # 2. Logic for Deep Link "reg" (if used explicitly)
    if args == "reg":
        if user:
            await message.answer("Вы уже зарегистрированы! ✅\nИспользуйте кнопки в чате, чтобы записаться на игру.")
            return
        # If not user, fall through to registration
    
    # Check for game deep link
    game_id = None
    if args and args.startswith("game_"):
        try:
            game_id = int(args.split("_")[1])
        except ValueError:
            pass

    # 3. If User Exists -> Show Menu OR Game
    if user:
        if game_id:
            # Show Game Interface
            game_result = await session.execute(select(Game).where(Game.id == game_id))
            game = game_result.scalar_one_or_none()
            if game:
                text = await format_game_message(game, session)
                await message.answer(text, reply_markup=get_game_keyboard(game_id))
                return
            else:
                await message.answer("Игра не найдена. 🤷‍♂️")
                
        # Check if admin
        is_admin = message.from_user.id in settings.ADMIN_IDS
        await message.answer("Привет! Я футбольный менеджер. ⚽\nИспользуйте команды или кнопки в чате.", reply_markup=get_main_menu_keyboard(is_admin))
        return

    # 4. If User NOT Exists -> Registration Flow
    if game_id:
        await state.update_data(pending_game_id=game_id)
        
    await message.answer("Добро пожаловать в Football Manager! ⚽\n\nДавайте создадим ваш профиль.\nКак вас зовут? (Введите Имя Фамилия)")
    await state.set_state(Registration.waiting_for_name)

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
    
    # Check if they only selected one, skipping primary selection? NOT REQUESTED but UX friendly?
    # No, prompt says "Main role + Alt roles". Always ask Main.
    
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
    
    # Save to DB
    new_user = User(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=full_name,
        player_position=Position(position_value),
        alt_positions=alt_positions
    )
    session.add(new_user)
    await session.commit()
    
    await callback.message.edit_text(f"Регистрация успешна! ✅\n\n👤 {full_name}\n📍 {position_value}")
    await state.clear()
    
    # Redirect to pending game if any
    if pending_game_id:
        game_result = await session.execute(select(Game).where(Game.id == pending_game_id))
        game = game_result.scalar_one_or_none()
        if game:
            text = await format_game_message(game, session)
            await callback.message.answer(text, reply_markup=get_game_keyboard(pending_game_id))
        else:
            await callback.message.answer("Игра, которую вы искали, не найдена, но вы теперь зарегистрированы!")

@router.message(Command("history"))
async def cmd_history(message: types.Message):
    # Мы берем ID текущего чата, где написали команду
    current_chat_id = message.chat.id
    
    # Формируем URL с параметром
    web_app_url = f"{settings.WEBAPP_URL}/web/history.html?chat_id={current_chat_id}"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="📜 Открыть архив игр", 
            web_app=types.WebAppInfo(url=web_app_url)
        )]
    ])
    
    await message.answer(
        "Нажмите кнопку ниже, чтобы посмотреть статистику именно этого чата:",
        reply_markup=kb
    )

@router.message(F.text == "👤 Мой профиль")
@router.message(Command("my_profile"))
async def cmd_my_profile(message: types.Message, session: AsyncSession):
    user_id = message.from_user.id
    user = await session.get(User, user_id)
    
    if not user:
        await message.answer("Вы еще не зарегистрированы. Нажмите /start")
        return

    # Calculate total goals
    try:
        total_goals = await session.scalar(
            select(func.sum(GameStats.goals)).where(GameStats.user_id == user_id)
        ) or 0
    except Exception as e:
        print(f"Error calculating goals: {e}")
        total_goals = 0

    text = f"👤 <b>Профиль игрока</b>\n\n"
    text += f"<b>{user.full_name}</b> (@{user.username or 'нет'})\n"
    text += f"📍 Позиция: <b>{user.player_position.value}</b>\n"
    
    if user.alt_positions:
        text += f"🔄 Доп. позиции: {', '.join(user.alt_positions)}\n"
    
    text += f"➖➖➖➖➖➖➖➖\n"
    
    if settings.SHOW_RATING:
        text += f"📊 Рейтинг: <b>{user.rating}</b>\n"
    
    text += f"🎮 Матчей: <b>{user.games_played}</b>\n"
    text += f"⭐️ MVP: <b>{user.stats_mvp}</b>\n"
    text += f"⚽ Голов: <b>{total_goals}</b>"
    
    await message.answer(text)

@router.message(F.text == "📜 Мои матчи")
@router.message(Command("my_history"))
async def cmd_my_history(message: types.Message, session: AsyncSession):
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
        await message.answer("Вы еще не сыграли ни одного матча. Записывайтесь скорее!")
        return

    # 2. Формируем красивый текст
    text = "<b>📜 Ваши последние игры:</b>\n\n"

    for game, signup, stats, rating in matches:
        # А. Определяем результат (Победа/Поражение)
        result_icon = "🤝" # Ничья по дефолту
        if game.winner_team:
            if game.winner_team == signup.team:
                result_icon = "🏆" # Победа
            else:
                result_icon = "💀" # Поражение
        
        # Б. Счет матча
        score_text = f"{game.score_a or 0}:{game.score_b or 0}"
        
        # В. Строка матча
        date_str = game.date_time.strftime("%d.%m")
        text += f"{result_icon} <b>{date_str} | {game.location}</b> ({score_text})\n"
        
        # Г. Личная статистика (Детали)
        details = []
        
        # Голы
        if stats and stats.goals > 0:
            details.append(f"⚽ {stats.goals}")
            
        # Рейтинг (Shadow ELO check)
        if settings.SHOW_RATING and rating:
            sign = "+" if rating.change > 0 else ""
            details.append(f"📈 {sign}{rating.change} MMR")
        
        # Если были детали, добавляем их
        if details:
            text += f"   └ <i>{' • '.join(details)}</i>\n"
        else:
            text += "   └ <i>Без результативных действий</i>\n"
            
        text += "\n"

    # Добавляем общую стату в подвал
    user = await session.get(User, user_id)
    text += f"➖➖➖➖➖➖➖➖\n"
    text += f"👤 <b>{user.full_name}</b>\n"
    
    if settings.SHOW_RATING:
        text += f"📊 Рейтинг: <b>{user.rating}</b>\n"
        
    text += f"🎮 Матчей: <b>{user.games_played}</b>"

    await message.answer(text)
