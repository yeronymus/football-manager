import html
import logging
import re
from aiogram import Router, types, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.fsm import GuestAddition
from app.bot.i18n import t
from app.bot.keyboards import get_game_keyboard
from app.config import settings
from app.core.repositories.user_repository import UserRepository
from app.db.models import Game, Language, User, Signup, SignupStatus, Team

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.is_automatic_forward == True)
async def handle_auto_forward(message: types.Message, session: AsyncSession):
    game_id = None

    all_entities = (message.entities or []) + (message.caption_entities or [])

    for entity in all_entities:
        if entity.type == "text_link" and entity.url:
            match = re.search(r"start=game_(\d+)", entity.url)
            if match:
                game_id = int(match.group(1))
                break

    if not game_id:
        text_to_check = message.text or message.caption or ""
        match = re.search(r"start=game_(\d+)", text_to_check)
        if match:
            game_id = int(match.group(1))

    if not game_id:
        return

    result = await session.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()

    if game:
        if message.forward_from_chat:
            game.channel_id = message.forward_from_chat.id
            game.channel_message_id = message.forward_from_message_id

        if game.chat_id == message.chat.id and game.message_id:
            try:
                await message.delete()
                logger.info(f"Duplicate forward for game {game_id} in current chat. Silently deleted.")
            except Exception as e:
                logger.warning(f"Failed to delete duplicate forward: {e}")
            return

        try:
            await message.delete()

            is_admin = False
            if message.from_user and (
                message.from_user.id in settings.admin_ids
                or message.from_user.id == settings.system_owner_id
            ):
                is_admin = True

            from app.bot.utils import resolve_chat_language, format_game_message
            chat_lang = await resolve_chat_language(session, message.chat.id)

            text_short = await format_game_message(game, session, is_short=True, lang=chat_lang)
            kb = get_game_keyboard(game_id, is_admin=is_admin, webapp_url=settings.webapp_url, lang=chat_lang)

            sent_msg = await message.bot.send_message(
                chat_id=message.chat.id,
                text=text_short,
                reply_markup=kb,
                parse_mode="HTML",
            )

            logger.info(f"Successfully replaced auto-forward with message {sent_msg.message_id} in {message.chat.id}")

            game.chat_id = message.chat.id
            game.message_id = sent_msg.message_id
            await session.commit()

            try:
                await message.bot.pin_chat_message(chat_id=message.chat.id, message_id=sent_msg.message_id)
            except Exception:
                pass

            return
        except Exception as e:
            logger.info(f"Failed to replace auto-forward: {e}. Falling back to reply.")

        if game.chat_id == message.chat.id:
            logger.info(f"Duplicate forward for game {game_id} in current chat. Ignoring.")
            return

        chat_lang = await resolve_chat_language(session, message.chat.id)
        short_text = t("tap_to_signup", locale=chat_lang)
        try:
            sent_msg = await message.reply(
                short_text,
                reply_markup=get_game_keyboard(game_id, lang=chat_lang),
                parse_mode="HTML",
            )
            game.chat_id = message.chat.id
            game.message_id = sent_msg.message_id
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to reply to auto-forward: {e}")


@router.message(Command("refresh_game"))
async def cmd_refresh_game(message: types.Message, command: CommandObject, session: AsyncSession):
    if (
        message.from_user.id not in settings.admin_ids
        and message.from_user.id != settings.system_owner_id
    ):
        return

    user_lang = "ru"
    if message.from_user.language_code and not message.from_user.language_code.startswith("ru"):
        user_lang = "en"

    try:
        game_id = int(command.args)
    except Exception:
        await message.answer(t("cmd_refresh_usage", locale=user_lang))
        return

    game = await session.get(Game, game_id)
    if not game:
        await message.answer(t("game_not_found", locale=user_lang))
        return

    from app.bot.utils import update_game_message

    try:
        await update_game_message(message.bot, game, session)
        await message.answer(
            t("game_refreshed_success", locale=user_lang, game_num=game_id),
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(
            t("game_refresh_error", locale=user_lang, game_num=game_id, error=str(e)),
            parse_mode="HTML",
        )


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
    await state.clear()

    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
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

    # 2. Logic for Deep Link "reg"
    if args == "reg":
        if user:
            await message.answer(t("already_registered_notice", locale=user_lang))
            return

    game_id = None
    action_type = "game"

    if args:
        if args.startswith("game_"):
            try:
                game_id = int(args.split("_")[1])
                action_type = "game"
            except ValueError:
                pass
        elif args.startswith("finish_") or args.startswith("edit_"):
            try:
                game_id = int(args.split("_")[1])
                base = settings.webapp_url.rstrip("/")
                if args.startswith("finish_"):
                    web_url = f"{base}/web/finish.html?game_id={game_id}&mode=edit&v={settings.webapp_version}"
                    label = t("btn_fill_results", locale=user_lang)
                else:
                    web_url = f"{base}/web/edit_game.html?game_id={game_id}&v={settings.webapp_version}"
                    label = t("btn_open_editor", locale=user_lang)

                kb = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [types.InlineKeyboardButton(text=label, web_app=types.WebAppInfo(url=web_url))]
                    ]
                )
                await message.answer(
                    t("game_mgmt_title", locale=user_lang, game_num=game_id),
                    reply_markup=kb,
                )
                return
            except (ValueError, IndexError):
                pass
        elif args.startswith("addguest_"):
            try:
                game_id = int(args.split("_")[1])
                action_type = "addguest"
            except (ValueError, IndexError):
                pass

    # 3. If User Exists
    if user:
        if game_id:
            result = await session.execute(select(Game).where(Game.id == game_id))
            game = result.scalar_one_or_none()

            is_admin = False
            is_member = False

            if (
                message.from_user.id in settings.admin_ids
                or message.from_user.id == settings.system_owner_id
            ):
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
                text_denied = t("denied_private_group_msg", locale=user_lang)
                btn_contact = t("btn_contact_organizer", locale=user_lang)
                btn_retry = t("btn_i_am_in_group", locale=user_lang)

                bot_username = settings.bot_username
                buttons = [
                    [types.InlineKeyboardButton(text=btn_contact, url="https://t.me/yeronymus")],
                    [types.InlineKeyboardButton(text=btn_retry, url=f"https://t.me/{bot_username}?start=game_{game_id}")],
                ]

                await message.answer(
                    text_denied,
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
                    parse_mode="HTML",
                )
                return

            from app.bot.utils import get_group_game_number

            game_num = await get_group_game_number(session, game) if game else game_id

            if action_type == "edit":
                if not is_admin:
                    await message.answer(t("only_for_admins", locale=user_lang))
                    return
                web_app_url = f"{settings.webapp_url.rstrip('/')}/web/edit_game.html?game_id={game_id}&v={settings.webapp_version}"
                kb = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text=t("btn_open_editor_webapp", locale=user_lang),
                                web_app=types.WebAppInfo(url=web_app_url),
                            )
                        ]
                    ]
                )
                await message.answer(
                    t("edit_game_title", locale=user_lang, game_num=game_num),
                    reply_markup=kb,
                    parse_mode="HTML",
                )
                return

            elif action_type == "finish":
                if not is_admin:
                    await message.answer(t("only_for_admins", locale=user_lang))
                    return
                web_app_url = f"{settings.webapp_url.rstrip('/')}/web/finish.html?game_id={game_id}&v={settings.webapp_version}"
                kb = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text=t("btn_open_finish_webapp", locale=user_lang),
                                web_app=types.WebAppInfo(url=web_app_url),
                            )
                        ]
                    ]
                )
                await message.answer(
                    t("finish_game_title", locale=user_lang, game_num=game_num),
                    reply_markup=kb,
                    parse_mode="HTML",
                )
                return

            elif action_type == "vote":
                result = await session.execute(
                    select(User, Signup.team)
                    .join(Signup)
                    .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
                )
                players_data = result.all()
                if not players_data:
                    await message.answer(t("vote_no_players", locale=user_lang))
                    return

                team_a = []
                team_b = []
                team_c = []
                unassigned = []
                for u, t_val in players_data:
                    if t_val == Team.A:
                        team_a.append(u)
                    elif t_val == Team.B:
                        team_b.append(u)
                    elif t_val == Team.C:
                        team_c.append(u)
                    else:
                        unassigned.append(u)

                from app.bot.keyboards import get_voting_keyboard

                kb = get_voting_keyboard(
                    game_id, team_a, team_b, team_c=team_c, unassigned=unassigned, lang=user_lang
                )
                v_text = t("cmd_start_voting_title", locale=user_lang, game_num=game_num)
                await message.answer(v_text, reply_markup=kb)
                return

            elif action_type == "addguest":
                if not is_admin:
                    await message.answer(t("only_for_admins", locale=user_lang))
                    return
                await state.update_data(guest_game_id=game_id)
                await state.set_state(GuestAddition.waiting_for_name)
                await message.answer(
                    t("guest_add_prompt", locale=user_lang, game_num=game_num),
                    parse_mode="HTML",
                )
                return

            # Show Game Interface
            try:
                result = await session.execute(select(Game).where(Game.id == game_id))
                game = result.scalar_one_or_none()
                if game:
                    from app.bot.utils import format_game_message, resolve_chat_language

                    match_lang = await resolve_chat_language(session, game.chat_id)
                    text = await format_game_message(game, session, lang=match_lang)
                    kb = get_game_keyboard(game_id, is_admin=is_admin, lang=match_lang)
                    await message.answer(text, reply_markup=kb)
                    return
                else:
                    await message.answer(t("game_not_found", locale=user_lang))
                    return
            except Exception as e:
                logger.error(f"Error in cmd_start game logic: {e}", exc_info=True)
                await message.answer(f"⚠️ Ошибка при загрузке игры: {html.escape(str(e))}")
                return

        # Send Welcome Message
        welcome_text = t("welcome_already_registered", locale=user_lang)
        await message.answer(
            welcome_text,
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return

    # 4. If User NOT Exists -> Registration Flow
    chat_id = None
    if game_id:
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        if game:
            chat_id = game.chat_id

    reg_url = f"{settings.webapp_url.rstrip('/')}/web/register.html?v={settings.webapp_version}"
    if chat_id:
        reg_url += f"&chat_id={chat_id}"
    if game_id:
        reg_url += f"&game_id={game_id}"

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=t("btn_create_profile", locale=user_lang),
                    web_app=types.WebAppInfo(url=reg_url),
                )
            ],
            [
                types.InlineKeyboardButton(text="🇬🇧 English", callback_data="userlang_en"),
                types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="userlang_ru"),
            ],
        ]
    )

    await message.answer(
        t("welcome_unregistered_intro", locale=user_lang),
        reply_markup=kb,
        parse_mode="HTML",
    )
