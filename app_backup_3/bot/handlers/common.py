from aiogram import Router, types, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import User, Game
from app.config import settings
from app.core.repositories.user_repository import UserRepository
from app.bot.keyboards import get_game_keyboard
from app.bot.fsm import Registration
import logging
import re
import html

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
            if message.forward_from_chat:
                game.channel_id = message.forward_from_chat.id
                game.channel_message_id = message.forward_from_message_id
            
            # --- Attempt to add buttons to the forward itself ---
            # If the bot posted the message in the channel and is an admin in the group, 
            # it can edit the forward in the group directly. This avoids duplicate messages.
            try:
                kb = get_game_keyboard(game_id)
                await message.edit_reply_markup(reply_markup=kb)
                logger.info(f"Successfully added buttons to auto-forward message {message.message_id} in {message.chat.id}")
                
                # Use this message as the primary one for this chat
                game.chat_id = message.chat.id
                game.message_id = message.message_id
                await session.commit()
                return # No need to reply, we have buttons on the list!
            except Exception as e:
                logger.info(f"Failed to edit auto-forward markup: {e}. Falling back to reply.")

            # --- Avoid Duplicates ---
            # If we already have a reasonably fresh message in this chat, or if this is the FIRST time we see it here:
            if game.chat_id == message.chat.id:
                 logger.info(f"Duplicate forward for game {game_id} in current chat. Ignoring.")
                 return

            # Fallback: Send a compact message with buttons
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

@router.message(Command("refresh_game"))
async def cmd_refresh_game(message: types.Message, command: CommandObject, session: AsyncSession):
    # Only admins
    from app.config import settings
    if message.from_user.id not in settings.admin_ids and message.from_user.id != settings.system_owner_id:
        return
        
    try:
        game_id = int(command.args)
    except:
        await message.answer("Использование: /refresh_game <id>")
        return
        
    game = await session.get(Game, game_id)
    if not game:
        await message.answer("Игра не найдена.")
        return
        
    from app.bot.utils import format_game_message
    from app.bot.keyboards import get_game_keyboard
    
    text = await format_game_message(game, session)
    kb = get_game_keyboard(game.id)
    
    # Try to refresh messages
    reports = []
    
    async def try_edit(chat_id, msg_id, label):
        if not chat_id or not msg_id:
            return f"❌ {label}: Нет ID"
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML"
            )
            return f"✅ {label}: Сообщение обновлено"
        except Exception as e:
            return f"⚠️ {label}: Ошибка ({e})"

    rep1 = await try_edit(game.chat_id, game.message_id, "Группа")
    rep2 = await try_edit(game.channel_id, game.channel_message_id, "Канал")
    
    await message.answer(f"🔄 <b>Обновление игры #{game_id}:</b>\n\n{rep1}\n{rep2}", parse_mode="HTML")

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

async def cmd_start(message: types.Message, command: CommandObject, state: FSMContext, session: AsyncSession):
    """
    Unified /start handler.
    Matches both /start and /start <args> (deep links).
    """
    # Clean up the command message itself (UX)
    try:
        await message.delete()
    except:
        pass

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
    user_repo = UserRepository(session)
    user = await user_repo.get_user(message.from_user.id)

    # 2. Logic for Deep Link "reg" (if used explicitly)
    if args == "reg":
        if user:
            await message.answer("Вы уже зарегистрированы! ✅\nИспользуйте кнопки в чате, чтобы записаться на игру.")
            return
        # If not user, fall through to registration
    
    # Check for game deep link
    game_id = None
    action_type = "game" # default
    
    if args:
        if args.startswith("game_"):
            try:
                game_id = int(args.split("_")[1])
                action_type = "game"
            except ValueError: pass
        elif args.startswith("edit_"):
            try:
                game_id = int(args.split("_")[1])
                action_type = "edit"
            except ValueError: pass
            except ValueError: pass
        elif args.startswith("finish_"):
            try:
                game_id = int(args.split("_")[1])
                action_type = "finish"
            except ValueError: pass
        elif args.startswith("vote_"):
            try:
                game_id = int(args.split("_")[1])
                action_type = "vote"
            except ValueError: pass

    # 3. If User Exists -> Show Menu OR Game Action
    if user:
        if game_id:
            # Fetch Game First
            result = await session.execute(select(Game).where(Game.id == game_id))
            game = result.scalar_one_or_none()
            
            # Determine Admin Status (Dynamic)
            from app.config import settings
            is_admin = False
            
            if message.from_user.id in settings.admin_ids or message.from_user.id == settings.system_owner_id:
                is_admin = True
            elif game:
                try:
                    chat_member = await message.bot.get_chat_member(game.chat_id, message.from_user.id)
                    if chat_member.status in ["administrator", "creator"]:
                        is_admin = True
                except Exception:
                    pass
            
            if action_type == "edit":
                if not is_admin:
                    await message.answer("⛔ Только для админов.")
                    return
                web_app_url = f"{settings.webapp_url}/web/edit_game.html?game_id={game_id}"
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="✏️ Открыть редактор (WebApp)", web_app=types.WebAppInfo(url=web_app_url))]
                ])
                await message.answer(f"✏️ <b>Редактирование игры #{game_id}</b>", reply_markup=kb)
                return
                
            elif action_type == "finish":
                if not is_admin:
                    await message.answer("⛔ Только для админов.")
                    return
                web_app_url = f"{settings.webapp_url}/web/finish.html?game_id={game_id}"
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🏁 Открыть завершение (WebApp)", web_app=types.WebAppInfo(url=web_app_url))]
                ])
                await message.answer(f"🏁 <b>Завершение игры #{game_id}</b>", reply_markup=kb)
                return

            elif action_type == "vote":
                web_app_url = f"{settings.webapp_url}/web/vote.html?game_id={game_id}"
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🏆 Голосовать (WebApp)", web_app=types.WebAppInfo(url=web_app_url))]
                ])
                await message.answer(f"🏆 <b>Голосование за MVP (Игра #{game_id})</b>\nНажмите кнопку ниже, чтобы выбрать игроков.", reply_markup=kb)
                return

            # Show Game Interface (default "game_" action)
            try:
                result = await session.execute(select(Game).where(Game.id == game_id))
                game = result.scalar_one_or_none()
                if game:
                    # 1. Generate full game message text
                    from app.bot.utils import format_game_message
                    text = await format_game_message(game, session)
                    
                    # 2. Get standard keyboard (which has Deep Link URL for draft)
                    kb = get_game_keyboard(game_id)
                    
                    # 3. If Admin (Calculated dynamically above)
                    
                    if is_admin:
                        # Clean UX: No Join/Leave buttons, just the tool they asked for.
                        web_app_url = f"{settings.webapp_url}/web/draft.html?game_id={game_id}&v=1.9"
                        kb = types.InlineKeyboardMarkup(inline_keyboard=[
                            [types.InlineKeyboardButton(text="🛠 Составы (Draft) [WebApp]", web_app=types.WebAppInfo(url=web_app_url))]
                        ])
                    else:
                        # Non-admins gets standard view
                        kb = get_game_keyboard(game_id)

                    await message.answer(text, reply_markup=kb)
                    return
                else:
                    await message.answer("Игра не найдена. 🤷‍♂️")
            except Exception as e:
                logger.error(f"Error in cmd_start game logic: {e}", exc_info=True)
                await message.answer(f"⚠️ Ошибка при загрузке игры: {html.escape(str(e))}")
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
