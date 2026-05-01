from aiogram import Router, types, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import User, Game
from app.config import settings
from app.core.repositories.user_repository import UserRepository
from app.bot.keyboards import get_game_keyboard
from app.bot.fsm import Registration, GuestAddition
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
    
    # Check both text and caption entities
    all_entities = (message.entities or []) + (message.caption_entities or [])
    
    for entity in all_entities:
        if entity.type == "text_link" and entity.url:
            # Check for deep link format
            match = re.search(r"start=game_(\d+)", entity.url)
            if match:
                game_id = int(match.group(1))
                break
                
    # Fallback: Check raw text/caption for the link string (less reliable for hidden links)
    if not game_id:
        text_to_check = message.text or message.caption or ""
        match = re.search(r"start=game_(\d+)", text_to_check)
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
            
            # --- Attempt to replace the forward with our own message ---
            try:
                from app.bot.keyboards import get_game_keyboard
                from app.bot.utils import format_game_message
                
                # Удаляем пересланное сообщение из канала
                await message.delete()
                
                # Проверка статуса админа (чтобы кнопки появились сразу в группе)
                is_admin = False
                if message.from_user.id in settings.admin_ids or message.from_user.id == settings.system_owner_id:
                    is_admin = True
                
                # Формируем и отправляем новое сообщение с кнопками
                text_short = await format_game_message(game, session, is_short=True)
                kb = get_game_keyboard(game_id, is_admin=is_admin, webapp_url=settings.webapp_url)
                
                sent_msg = await message.bot.send_message(
                    chat_id=message.chat.id,
                    text=text_short,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                
                logger.info(f"Successfully replaced auto-forward with message {sent_msg.message_id} in {message.chat.id}")
                
                # Обновляем ID сообщения в базе, чтобы бот мог его редактировать при записи
                game.chat_id = message.chat.id
                game.message_id = sent_msg.message_id
                await session.commit()
                
                # Пробуем закрепить
                try:
                    await message.bot.pin_chat_message(chat_id=message.chat.id, message_id=sent_msg.message_id)
                except:
                    pass
                    
                return
            except Exception as e:
                logger.info(f"Failed to replace auto-forward: {e}. Falling back to reply.")

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
        "👤 <b>Как посмотреть профиль и статистику?</b>\n"
        "Перейдите в ЛС с ботом и используйте кнопку меню (Меню -> Мой Профиль).\n\n"
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
    # Clean up the command message itself (UX)
    # try:
    #     await message.delete()
    # except:
    #     pass

    # Always reset any stale FSM state (e.g. stuck registration in Redis)
    await state.clear()

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
        elif args.startswith("finish_") or args.startswith("edit_"):
            try:
                game_id = int(args.split("_")[1])
                # Constructed correct WebApp URL (mode=edit for finish.html)
                base = settings.webapp_url.rstrip("/")
                if args.startswith("finish_"):
                    web_url = f"{base}/web/finish.html?game_id={game_id}&mode=edit"
                    label = "🏁 Заполнить результаты"
                else:
                    web_url = f"{base}/web/edit_game.html?game_id={game_id}&v=1.3"
                    label = "✏️ Открыть редактор"
                
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=label, web_app=types.WebAppInfo(url=web_url))]
                ])
                await message.answer(f"🛠 Управление игрой #{game_id}:", reply_markup=kb)
                return
            except (ValueError, IndexError): pass
            except ValueError: pass
        elif args.startswith("addguest_"):
            try:
                game_id = int(args.split("_")[1])
                action_type = "addguest"
            except (ValueError, IndexError): pass

    # 3. If User Exists -> Show Menu OR Game Action
    if user:
        if game_id:
            # Fetch Game First
            result = await session.execute(select(Game).where(Game.id == game_id))
            game = result.scalar_one_or_none()
            
            # Determine Admin Status (Dynamic)
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
                web_app_url = f"{settings.webapp_url.rstrip('/')}/web/edit_game.html?game_id={game_id}&v=1.3"
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="✏️ Открыть редактор (WebApp)", web_app=types.WebAppInfo(url=web_app_url))]
                ])
                await message.answer(f"✏️ <b>Редактирование игры #{game_id}</b>", reply_markup=kb)
                return
                
            elif action_type == "finish":
                if not is_admin:
                    await message.answer("⛔ Только для админов.")
                    return
                web_app_url = f"{settings.webapp_url.rstrip('/')}/web/finish.html?game_id={game_id}"
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🏁 Открыть завершение (WebApp)", web_app=types.WebAppInfo(url=web_app_url))]
                ])
                await message.answer(f"🏁 <b>Завершение игры #{game_id}</b>", reply_markup=kb)
                return

            elif action_type == "vote":
                web_app_url = f"{settings.webapp_url.rstrip('/')}/web/vote.html?game_id={game_id}"
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🏆 Голосовать (WebApp)", web_app=types.WebAppInfo(url=web_app_url))]
                ])
                await message.answer(f"🏆 <b>Голосование за MVP (Игра #{game_id})</b>\nНажмите кнопку ниже, чтобы выбрать игроков.", reply_markup=kb)
                return

            elif action_type == "addguest":
                if not is_admin:
                    await message.answer("⛔ Только для админов.")
                    return
                await state.update_data(guest_game_id=game_id)
                await state.set_state(GuestAddition.waiting_for_name)
                await message.answer(f"👤 <b>Добавление гостя в игру #{game_id}</b>\n\nВведите имя гостя:")
                return

            # Show Game Interface (default "game_" action)
            try:
                result = await session.execute(select(Game).where(Game.id == game_id))
                game = result.scalar_one_or_none()
                if game:
                    if is_admin:
                        # ULTRA-MINIMALISTIC INTERFACE FOR ADMINS
                        webapp_url = settings.webapp_url.rstrip("/")
                        web_url = f"{webapp_url}/web/draft.html?game_id={game_id}&v=2.2"
                        kb = types.InlineKeyboardMarkup(inline_keyboard=[
                            [types.InlineKeyboardButton(text="🛠 Составы (Draft)", web_app=types.WebAppInfo(url=web_url))]
                        ])
                        await message.answer(f"⚽ <b>Игра #{game_id}: Составы</b>", reply_markup=kb, parse_mode="HTML")
                        return

                    # 1. Generate full game message text for regular users
                    from app.bot.utils import format_game_message
                    text = await format_game_message(game, session)
                    
                    # 2. Keyboard (Join/Leave only)
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
            "Вся статистика и настройки профиля доступны <b>только здесь, в личных сообщениях</b>.\n"
            "Используйте кнопку «Меню» слева от поля ввода, чтобы открыть свой Профиль, Лидерборд или Историю матчей.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return

    # 4. If User NOT Exists -> Registration Flow (Mini App)
    chat_id = None
    if game_id:
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        if game:
            chat_id = game.chat_id

    reg_url = f"{settings.webapp_url.rstrip('/')}/web/register.html?v=1.0"
    if chat_id:
        reg_url += f"&chat_id={chat_id}"
    if game_id:
        reg_url += f"&game_id={game_id}"

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📝 Создать профиль (Mini App)", web_app=types.WebAppInfo(url=reg_url))]
    ])

    await message.answer(
        "👋 <b>Добро пожаловать в Football Manager!</b>\n\n"
        "Чтобы участвовать в играх и отслеживать статистику, нужно создать профиль игрока.\n\n"
        "Это займет всего 30 секунд в нашем приложении! 👇",
        reply_markup=kb,
        parse_mode="HTML"
    )
