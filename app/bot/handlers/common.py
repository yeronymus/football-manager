from aiogram import Router, types, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Game, Language, User, Signup, SignupStatus, Team, Chat
from app.config import settings
from app.core.repositories.user_repository import UserRepository
from app.bot.keyboards import get_game_keyboard
from app.bot.fsm import GuestAddition
import logging
import re
import html
import time

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
            
            # --- Avoid Duplicates & Clean Up forwards ---
            # If we already have the game posted directly in this chat, just delete the forward and exit!
            if game.chat_id == message.chat.id and game.message_id:
                try:
                    await message.delete()
                    logger.info(f"Duplicate forward for game {game_id} in current chat. Silently deleted.")
                except Exception as e:
                    logger.warning(f"Failed to delete duplicate forward: {e}")
                return
            
            # --- Attempt to replace the forward with our own message ---
            try:
                from app.bot.keyboards import get_game_keyboard
                from app.bot.utils import format_game_message
                # Delete the forwarded message from the channel
                await message.delete()
                
                # Check admin status (to show buttons in the group immediately)
                is_admin = False
                if message.from_user.id in settings.admin_ids or message.from_user.id == settings.system_owner_id:
                    is_admin = True
                
                chat_lang = "ru"
                chat_obj = await session.get(Chat, message.chat.id)
                if chat_obj and chat_obj.language:
                    chat_lang = chat_obj.language.value if hasattr(chat_obj.language, 'value') else str(chat_obj.language)
                chat_lang = (chat_lang or "ru").lower()
                
                # Format and send the new message with buttons
                text_short = await format_game_message(game, session, is_short=True, lang=chat_lang)
                kb = get_game_keyboard(game_id, is_admin=is_admin, webapp_url=settings.webapp_url, lang=chat_lang)
                
                sent_msg = await message.bot.send_message(
                    chat_id=message.chat.id,
                    text=text_short,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                
                logger.info(f"Successfully replaced auto-forward with message {sent_msg.message_id} in {message.chat.id}")
                
                # Update message ID in DB so the bot can edit it on registration changes
                game.chat_id = message.chat.id
                game.message_id = sent_msg.message_id
                await session.commit()
                
                # Try to pin
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
            from app.bot.i18n import t
            short_text = t("tap_to_signup", locale=chat_lang)
            try:
                sent_msg = await message.reply(
                    short_text,
                    reply_markup=get_game_keyboard(game_id, lang=chat_lang),
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
        
    from app.bot.utils import update_game_message
    
    try:
        await update_game_message(message.bot, game, session)
        await message.answer(f"🔄 <b>Игра #{game_id} успешно обновлена в группе и канале!</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ <b>Ошибка при обновлении игры #{game_id}:</b> {e}", parse_mode="HTML")

@router.message(Command("rules"))
@router.message(Command("info"))
async def cmd_rules(message: types.Message):
    text = (
        "📋 <b>How to Play & Group Rules / Как играть</b>\n\n"
        "🇬🇧 <b>ENGLISH:</b>\n"
        "1. <b>Be in the group:</b> Matches are organized exclusively in this group via the bot.\n"
        "2. <b>Profile:</b> Create your player profile once via the bot (takes 30 seconds).\n"
        "3. <b>Sign Up:</b> Click <b>Sign Up for Game</b> under the match card in the group.\n"
        "4. <b>Cancellation:</b> If you can't come, unregister at least 24h before kickoff so reserve players can take your spot.\n"
        "5. <b>Payment:</b> Pay match fee using the organizer's details shown in the game card.\n\n"
        "🇷🇺 <b>РУССКИЙ:</b>\n"
        "1. <b>Быть в группе:</b> Игры проводятся строго в этой группе через бота.\n"
        "2. <b>Профиль:</b> Создайте профиль игрока один раз в боте (занимает 30 секунд).\n"
        "3. <b>Запись:</b> Жмите кнопку <b>Записаться на игру</b> под постом матча в группе.\n"
        "4. <b>Отмена:</b> Если не получается прийти — выпишитесь минимум за 24ч до игры, чтобы освободить место резерву.\n"
        "5. <b>Оплата:</b> Переводите взнос за игру по реквизитам организатора из карточки матча."
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "🆘 <b>Help & FAQ / Помощь</b>\n\n"
        "🇬🇧 <b>ENGLISH:</b>\n"
        "• <b>Join game:</b> Click the sign-up button on the game post in the group.\n"
        "• <b>Profile & Stats:</b> Open bot in private chat -> Menu -> My Profile.\n"
        "• <b>Change language:</b> Send /language in private chat with the bot.\n"
        "• <b>Group rules:</b> Send /rules or /info.\n"
        "• <b>Support:</b> Contact @yeronymus\n\n"
        "🇷🇺 <b>РУССКИЙ:</b>\n"
        "• <b>Запись:</b> Кнопка «Записаться» под сообщением об игре в группе.\n"
        "• <b>Профиль:</b> В ЛС с ботом -> Меню -> Мой Профиль.\n"
        "• <b>Смена языка:</b> Отправьте /language в ЛС с ботом.\n"
        "• <b>Правила:</b> Команда /rules или /info.\n"
        "• <b>Поддержка:</b> Пишите @yeronymus"
    )
    await message.answer(help_text, parse_mode="HTML")

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
        return

    args = command.args
    
    # 1. Check User Existence
    user_repo = UserRepository(session)
    user = await user_repo.get_user(message.from_user.id)
    user_lang = "ru"
    if user and getattr(user, "language", None):
        user_lang = user.language.value if hasattr(user.language, "value") else str(user.language)
    elif message.from_user.language_code and not message.from_user.language_code.startswith("ru"):
        user_lang = "en"
    user_lang = (user_lang or "ru").lower()

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
                    web_url = f"{base}/web/edit_game.html?game_id={game_id}&_t={int(time.time())}"
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
            
            # Determine Admin and Member Status (Dynamic)
            is_admin = False
            is_member = False
            
            if message.from_user.id in settings.admin_ids or message.from_user.id == settings.system_owner_id:
                is_admin = True
                is_member = True
            elif game:
                try:
                    chat_member = await message.bot.get_chat_member(game.chat_id, message.from_user.id)
                    if chat_member.status in ["administrator", "creator"]:
                        is_admin = True
                        is_member = True
                    elif chat_member.status in ["member", "restricted"]:
                        is_member = True
                except Exception:
                    is_member = False
            
            if game and not is_member:
                # Private/closed group check: access by invitation only
                user_lang = getattr(user, 'language', 'en')
                user_lang = user_lang.value if hasattr(user_lang, 'value') else str(user_lang)
                is_user_en = (user_lang or 'en').lower() == 'en'
                
                if is_user_en:
                    text_denied = (
                        "⛔ <b>Private Group / Invitation Only</b>\n\n"
                        "Games are organized exclusively for members of our closed community.\n"
                        "To request an invitation to the group, please contact the organizer."
                    )
                    btn_contact = "✉️ Contact Organizer (@yeronymus)"
                    btn_retry = "🔄 I Am in the Group"
                else:
                    text_denied = (
                        "⛔ <b>Закрытая группа / Доступ по приглашению</b>\n\n"
                        "Матчи проводятся только для участников нашего закрытого сообщества.\n"
                        "Чтобы получить приглашение в группу, напишите организатору."
                    )
                    btn_contact = "✉️ Написать организатору (@yeronymus)"
                    btn_retry = "🔄 Я уже в группе"
                
                bot_username = settings.bot_username
                buttons = [
                    [types.InlineKeyboardButton(text=btn_contact, url="https://t.me/yeronymus")],
                    [types.InlineKeyboardButton(text=btn_retry, url=f"https://t.me/{bot_username}?start=game_{game_id}")]
                ]
                
                await message.answer(text_denied, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
                return
            
            from app.bot.utils import get_group_game_number
            game_num = await get_group_game_number(session, game) if game else game_id

            if action_type == "edit":
                if not is_admin:
                    await message.answer("⛔ Только для админов.")
                    return
                web_app_url = f"{settings.webapp_url.rstrip('/')}/web/edit_game.html?game_id={game_id}&_t={int(time.time())}"
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="✏️ Открыть редактор (WebApp)", web_app=types.WebAppInfo(url=web_app_url))]
                ])
                await message.answer(f"✏️ <b>Редактирование игры #{game_num}</b>", reply_markup=kb)
                return
                
            elif action_type == "finish":
                if not is_admin:
                    await message.answer("⛔ Только для админов.")
                    return
                web_app_url = f"{settings.webapp_url.rstrip('/')}/web/finish.html?game_id={game_id}"
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🏁 Открыть завершение (WebApp)", web_app=types.WebAppInfo(url=web_app_url))]
                ])
                await message.answer(f"🏁 <b>Завершение игры #{game_num}</b>", reply_markup=kb)
                return

            elif action_type == "vote":
                result = await session.execute(
                    select(User, Signup.team)
                    .join(Signup)
                    .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
                )
                players_data = result.all()
                if not players_data:
                    await message.answer("⚠️ В этом матче нет игроков для голосования." if user_lang == "ru" else "⚠️ No players found for this match.")
                    return

                team_a = []
                team_b = []
                team_c = []
                unassigned = []
                for u, t in players_data:
                    if t == Team.A: team_a.append(u)
                    elif t == Team.B: team_b.append(u)
                    elif t == Team.C: team_c.append(u)
                    else: unassigned.append(u)

                from app.bot.keyboards import get_voting_keyboard
                from app.bot.i18n import t
                kb = get_voting_keyboard(game_id, team_a, team_b, team_c=team_c, unassigned=unassigned, lang=user_lang)
                v_text = t("cmd_start_voting_title", locale=user_lang, game_num=game_num)
                await message.answer(v_text, reply_markup=kb)
                return

            elif action_type == "addguest":
                if not is_admin:
                    await message.answer("⛔ Только для админов.")
                    return
                await state.update_data(guest_game_id=game_id)
                await state.set_state(GuestAddition.waiting_for_name)
                await message.answer(f"👤 <b>Добавление гостя в игру #{game_num}</b>\n\nВведите имя гостя:")
                return

            # Show Game Interface (default "game_" action)
            try:
                result = await session.execute(select(Game).where(Game.id == game_id))
                game = result.scalar_one_or_none()
                if game:
                    # 1. Generate full game message text
                    from app.bot.utils import format_game_message
                    text = await format_game_message(game, session, lang=user_lang)
                    
                    # 2. Keyboard (includes Draft button for admins)
                    kb = get_game_keyboard(game_id, is_admin=is_admin, lang=user_lang)
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
        is_en = (getattr(user, 'language', None) == 'en' or getattr(user, 'language', None) == Language.en)
        if is_en:
            welcome_text = (
                "✅ <b>You are already registered!</b>\n\n"
                "All your statistics and profile settings are available <b>here in private messages</b>.\n"
                "Use the «Menu» button to open your Profile, Leaderboard, or Match History."
            )
        else:
            welcome_text = (
                "✅ <b>Вы уже зарегистрированы!</b>\n\n"
                "Вся статистика и настройки профиля доступны <b>только здесь, в личных сообщениях</b>.\n"
                "Используйте кнопку «Меню» слева от поля ввода, чтобы открыть свой Профиль, Лидерборд или Историю матчей."
            )
        await message.answer(
            welcome_text,
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode="HTML"
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
        [types.InlineKeyboardButton(text="📝 Create Profile / Создать профиль", web_app=types.WebAppInfo(url=reg_url))],
        [
            types.InlineKeyboardButton(text="🇬🇧 English", callback_data="userlang_en"),
            types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="userlang_ru")
        ]
    ])

    await message.answer(
        "👋 <b>Welcome to Football Manager! / Добро пожаловать!</b>\n\n"
        "🇬🇧 To join games and track your statistics, please create your player profile.\n"
        "🇷🇺 Чтобы участвовать в играх и отслеживать статистику, создайте профиль игрока.\n\n"
        "⚡ It only takes 30 seconds! / Это займет 30 секунд! 👇",
        reply_markup=kb,
        parse_mode="HTML"
    )
