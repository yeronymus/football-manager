from aiogram import Router, types, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import User, Game
from app.config import settings
from app.services.user_service import UserService
from app.bot.keyboards import get_game_keyboard
from app.bot.fsm import Registration
import logging
import re

logger = logging.getLogger(__name__)

router = Router()

@router.message(F.is_automatic_forward == True)
async def handle_auto_forward(message: types.Message, session: AsyncSession):
    # Ignore if somehow triggered by bot itself (though auto_forward usually implies channel->group)
    # Channel posts might appear as bot (Telegram Service), so we should NOT return here blindly.
    # We rely on F.is_automatic_forward == True which is robust.
    
    game_id = None
    
    # Strategy 1: Look for Text Links in Entities
    if message.entities:
        for entity in message.entities:
            if entity.type == "text_link" and entity.url:
                match = re.search(r"start=game_(\d+)", entity.url)
                if match:
                    game_id = int(match.group(1))
                    break
    
    # Strategy 2: If no entity link, maybe it's in the text (unlikely for hidden link, but possible if raw link posted)
    if not game_id and message.text:
            match = re.search(r"start=game_(\d+)", message.text)
            if match:
                game_id = int(match.group(1))
                
    if not game_id:
        return
    
    if game_id:
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        
        if game:
            from app.bot.utils import format_game_message
            text = await format_game_message(game, session)
            
            # --- Capture Source Info ---
            # If this is a forward from a channel, we want to know its IDs for sync
            if message.forward_from_chat:
                game.channel_id = message.forward_from_chat.id
                game.channel_message_id = message.forward_from_message_id
            
            # --- Avoid Duplicates ---
            # If we already have a reasonably fresh message in this chat, or if this is the FIRST time we see it here:
            # The user says "one is extra". If the forwarded message itself is usable, we use it.
            # But we can't add buttons to someone else's forward easily if we don't own it?
            # Actually, if the BOT posted to the channel, the forward IS the bot's message.
            
            # If the forwarded message already has buttons, we don't need a reply!
            if message.reply_markup and message.reply_markup.inline_keyboard:
                logger.info(f"Auto-forward for game {game_id} already has buttons. Updating group reference.")
                game.chat_id = message.chat.id
                game.message_id = message.message_id
                await session.commit()
                return

            # If it's a "silent" forward (no buttons), we might need to send our control message.
            # But the user says they see TWO. This means the forward AND the bot's reply.
            # If the user wants ONE, we should probably just NOT reply and let them use the link?
            # No, buttons are better.
            
            # Let's check if we recently sent a message here.
            # For now, let's just make it silent if it's an auto-forward and we are already tracking it.
            if game.chat_id == message.chat.id:
                logger.info(f"Duplicate forward for game {game_id} in same chat. Ignoring.")
                return

            short_text = "👇 <b>Нажмите, чтобы записаться:</b>"
            try:
                sent_msg = await message.reply(
                    short_text,
                    reply_markup=get_game_keyboard(game_id),
                    parse_mode="HTML"
                )
                
                # Update game tracking
                game.chat_id = message.chat.id
                game.message_id = sent_msg.message_id
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to reply to auto-forward: {e}")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🆘 <b>Помощь</b>\n\n"
        "⚽ <b>Как записаться на игру?</b>\n"
        "Просто нажмите кнопку <b>Записаться</b> под сообщением об игре в группе.\n\n"
        "👤 <b>Как зарегистрироваться?</b>\n"
        "Нажмите /start и введите свое имя.\n\n"
        "⚙️ <b>Проблемы?</b>\n"
        "Пишите @yeronymus (Разработчик)",
        parse_mode="HTML"
    )

@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject, state: FSMContext, session: AsyncSession):
    """
    Unified /start handler.
    Matches both /start and /start <args> (deep links).
    """
    # Security: Prevent /start in groups from triggering registration flow
    if message.chat.type != "private":
        # Delete the command to clean up chat (optional, but good for anti-spam)
        try:
            await message.delete()
        except:
            pass
            
        # Send a self-destructing prompt to go to private
        # USER REQUEST: Silent in groups. Just delete.
        # bot = await message.bot.get_me()
        # msg = await message.answer(
        #     f"👋 Привет! Чтобы использовать бота, напишите мне в ЛС:\n\n👉 t.me/{bot.username}?start=reg",
        #     disable_web_page_preview=True
        # )
        return

    args = command.args
    
    # 1. Check User Existence
    user_service = UserService(session)
    user = await user_service.get_user(message.from_user.id)

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
            result = await session.execute(select(Game).where(Game.id == game_id))
            game = result.scalar_one_or_none()
            if game:
                from app.bot.utils import format_game_message
                text = await format_game_message(game, session)
                await message.answer(text, reply_markup=get_game_keyboard(game_id))
                return
            else:
                await message.answer("Игра не найдена. 🤷‍♂️")
                
        # 2. Send Welcome Message
        await message.answer(
            "✅ <b>Вы уже зарегистрированы!</b>\n\n"
            "Вы можете посмотреть свои матчи (/history) и профиль (/profile) через меню команд.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return

    # 4. If User NOT Exists -> Registration Flow
    if game_id:
        await state.update_data(pending_game_id=game_id)
        
    
    # 5. Clarify Registration
    await message.answer(
        "👋 <b>Добро пожаловать в Football Manager!</b>\n\n"
        "Давай создадим твой профиль игрока.\n\n"
        "📝 <b>Как тебя зовут?</b>\n👇 Напиши свое Имя и Фамилию ниже в чат (латинницей)",
    )
    await state.set_state(Registration.waiting_for_name)
