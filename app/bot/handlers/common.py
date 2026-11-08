import html
import logging
import re

from aiogram import F, Router, types
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.fsm import GuestAddition
from app.bot.i18n import i18n_instance, t
from app.bot.keyboards import get_game_keyboard
from app.config import settings
from app.core.domain.tenant_policy import OrganizerContact, resolve_tenant_policy
from app.core.i18n import normalize_locale_code
from app.core.repositories.user_repository import UserRepository
from app.db.models import Chat, Game, Signup, SignupStatus, Team, User

logger = logging.getLogger(__name__)

router = Router()


def _resolve_event_lang(tg_user: types.User | None, db_user: User | None = None) -> str:
    if db_user and getattr(db_user, "language", None):
        return i18n_instance.catalog.resolve_supported(db_user.language)
    lang_code = getattr(tg_user, "language_code", None)
    if isinstance(lang_code, str) and lang_code.strip():
        return i18n_instance.catalog.resolve_supported(lang_code)
    return normalize_locale_code(settings.default_locale, default="en")


def _resolve_contact_url(chat: Chat | None) -> str | None:
    policy = resolve_tenant_policy(getattr(chat, "policy", None) if chat else None)
    for contact in policy.organizer_contacts:
        url = contact.resolved_url()
        if url:
            return url
    raw_support = (settings.support_contact or "").strip()
    if raw_support:
        return OrganizerContact(name="Support", handle=raw_support).resolved_url()
    return None


@router.message(F.is_automatic_forward == True)
async def handle_auto_forward(message: types.Message, session: AsyncSession):
    game_id = None

    all_entities = (message.entities or []) + (message.caption_entities or [])

    for entity in all_entities:
        if entity.type == "text_link" and entity.url:
            match = re.search(r"start(?:app)?=game_(\d+)", entity.url)
            if match:
                game_id = int(match.group(1))
                break

    if not game_id:
        text_to_check = message.text or message.caption or ""
        match = re.search(r"start(?:app)?=game_(\d+)", text_to_check)
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
                logger.info(
                    f"Duplicate forward for game {game_id} in current chat. Silently deleted."
                )
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

            from app.bot.utils import format_game_message, resolve_chat_language

            chat_lang = await resolve_chat_language(session, message.chat.id)

            text_short = await format_game_message(game, session, is_short=True, lang=chat_lang)
            kb = get_game_keyboard(
                game_id, is_admin=is_admin, webapp_url=settings.webapp_url, lang=chat_lang
            )

            sent_msg = await message.bot.send_message(
                chat_id=message.chat.id,
                text=text_short,
                reply_markup=kb,
                parse_mode="HTML",
            )

            logger.info(
                f"Successfully replaced auto-forward with message {sent_msg.message_id} in {message.chat.id}"
            )

            game.chat_id = message.chat.id
            game.message_id = sent_msg.message_id
            await session.commit()

            try:
                await message.bot.pin_chat_message(
                    chat_id=message.chat.id, message_id=sent_msg.message_id
                )
            except Exception:
                pass

            return
        except Exception as e:
            logger.info(f"Failed to replace auto-forward: {e}. Falling back to reply.")

        if game.chat_id == message.chat.id:
            logger.info(f"Duplicate forward for game {game_id} in current chat. Ignoring.")
            return

        from app.bot.utils import resolve_chat_language

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

    user_lang = _resolve_event_lang(message.from_user)

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
async def cmd_rules(message: types.Message, session: AsyncSession | None = None):
    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        return

    db_user = None
    if session and message.from_user:
        try:
            db_user = await UserRepository(session).get_user(message.from_user.id)
        except Exception:
            db_user = None

    user_lang = _resolve_event_lang(message.from_user, db_user)
    rules_web_url = f"{settings.webapp_url.rstrip('/')}/web/rules.html?lang={user_lang}"
    btn = types.InlineKeyboardButton(
        text=t("cmd_rules_btn", locale=user_lang),
        web_app=types.WebAppInfo(url=rules_web_url),
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[btn]])

    text = t("cmd_rules_text", locale=user_lang, cancel_hours=24, rules_url=rules_web_url)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("help"))
async def cmd_help(message: types.Message, session: AsyncSession | None = None):
    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        return

    db_user = None
    if session and message.from_user:
        try:
            db_user = await UserRepository(session).get_user(message.from_user.id)
        except Exception:
            db_user = None

    user_lang = _resolve_event_lang(message.from_user, db_user)
    support = (settings.support_contact or "").strip()
    support_line = (
        t("cmd_help_support_line", locale=user_lang, contact=html.escape(support))
        if support
        else ""
    )
    help_text = t("cmd_help_text", locale=user_lang, support_line=support_line)
    await message.answer(help_text, parse_mode="HTML")


@router.message(CommandStart())
async def cmd_start(
    message: types.Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
):
    await state.clear()

    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        return

    args = command.args

    # 1. Check User Existence & Resolve Language (Universal Default: 'en')
    user_repo = UserRepository(session)
    user = await user_repo.get_user(message.from_user.id)
    user_lang = _resolve_event_lang(message.from_user, user)

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
        elif args.startswith("rules"):
            rules_lang = user_lang
            if "en" in args:
                rules_lang = "en"
            elif "ru" in args:
                rules_lang = "ru"
            elif "cs" in args or "cz" in args:
                rules_lang = "cs"
            rules_url = f"{settings.webapp_url.rstrip('/')}/web/rules.html?lang={rules_lang}"

            kb = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=t("btn_channel_rules", locale=user_lang),
                            web_app=types.WebAppInfo(url=rules_url),
                        )
                    ]
                ]
            )
            await message.answer(
                t("rules_intro_title", locale=user_lang),
                reply_markup=kb,
                parse_mode="HTML",
            )
            return
        elif args.startswith("finish_") or args.startswith("edit_"):
            try:
                game_id = int(args.split("_")[1])
                base = settings.webapp_url.rstrip("/")
                if args.startswith("finish_"):
                    web_url = f"{base}/web/finish.html?game_id={game_id}&mode=edit&v={settings.webapp_version}"
                    label = t("btn_fill_results", locale=user_lang)
                else:
                    web_url = (
                        f"{base}/web/edit_game.html?game_id={game_id}&v={settings.webapp_version}"
                    )
                    label = t("btn_open_editor", locale=user_lang)

                kb = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text=label, web_app=types.WebAppInfo(url=web_url)
                            )
                        ]
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
                    chat_member = await message.bot.get_chat_member(
                        game.chat_id, message.from_user.id
                    )
                    if chat_member.status in ["administrator", "creator"]:
                        is_admin = True
                        is_member = True
                    elif chat_member.status in ["member", "restricted"]:
                        is_member = True
                except Exception:
                    is_member = False

            if game and not is_member:
                text_denied = t("denied_private_group_msg", locale=user_lang)
                btn_retry = t("btn_i_am_in_group", locale=user_lang)

                chat_obj = None
                try:
                    maybe_chat = await session.get(Chat, game.chat_id)
                    if isinstance(maybe_chat, Chat):
                        chat_obj = maybe_chat
                except Exception:
                    chat_obj = None

                contact_url = _resolve_contact_url(chat_obj)
                bot_username = settings.bot_username
                buttons = []
                if contact_url:
                    btn_contact = t("btn_contact_organizer", locale=user_lang)
                    buttons.append([types.InlineKeyboardButton(text=btn_contact, url=contact_url)])
                buttons.append(
                    [
                        types.InlineKeyboardButton(
                            text=btn_retry,
                            url=f"https://t.me/{bot_username}?start=game_{game_id}",
                        )
                    ]
                )

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
                from app.db.models import Vote

                voted_res = await session.execute(
                    select(Vote.target_id).where(Vote.game_id == game_id, Vote.voter_id == user_id)
                )
                voted_target_ids = set(voted_res.scalars().all())

                kb = get_voting_keyboard(
                    game_id, team_a, team_b, team_c=team_c, unassigned=unassigned, lang=user_lang,
                    voted_target_ids=voted_target_ids
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
                try:
                    await message.delete()
                except Exception:
                    pass

                result = await session.execute(select(Game).where(Game.id == game_id))
                game = result.scalar_one_or_none()
                if game:
                    from app.bot.utils import _format_date, get_group_game_number

                    game_num = await get_group_game_number(session, game)
                    date_str = _format_date(game.date_time, lang=user_lang)

                    card_text = t(
                        "dm_game_signup_card",
                        locale=user_lang,
                        game_num=game_num,
                        date=date_str,
                        location=html.escape(game.location or ""),
                    )
                    kb = get_game_keyboard(game_id, is_admin=is_admin, lang=user_lang)
                    await message.answer(card_text, reply_markup=kb, parse_mode="HTML")
                    return
                else:
                    await message.answer(t("game_not_found", locale=user_lang))
                    return
            except Exception as e:
                logger.error(f"Error in cmd_start game logic: {e}", exc_info=True)
                await message.answer(
                    t("err_game_load_failed", locale=user_lang, error=html.escape(str(e)))
                )
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

    lang_buttons = [
        types.InlineKeyboardButton(
            text=f"{loc['flag']} {loc['name']}",
            callback_data=f"userlang_{loc['code']}",
        )
        for loc in i18n_instance.catalog.available_locales()
    ]
    lang_rows = [lang_buttons[i : i + 3] for i in range(0, len(lang_buttons), 3)]

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=t("btn_create_profile", locale=user_lang),
                    web_app=types.WebAppInfo(url=reg_url),
                )
            ],
            *lang_rows,
        ]
    )

    await message.answer(
        t("welcome_unregistered_intro", locale=user_lang),
        reply_markup=kb,
        parse_mode="HTML",
    )
