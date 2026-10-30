from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Game, Signup, User, SignupStatus, Team, GameStatus, Chat
import html
import time

def evict_game_signups_cache(game_id: int):
    """No-op kept for backwards compatibility."""
    pass

def format_positions(user, signup) -> str:
    main_pos = signup.position.value if signup.position else user.player_position.value
    if user.alt_positions:
        return f"{main_pos} ({', '.join(user.alt_positions)})"
    return main_pos


def _format_date(game_date_time, lang: str = "en") -> str:
    from app.core.timezone import to_prague_dt
    local_dt = to_prague_dt(game_date_time)
    if not local_dt:
        return ""
    
    if (lang or "en").lower() == "ru":
        days_map = {
            "Mon": "Пн", "Tue": "Вт", "Wed": "Ср", "Thu": "Чт",
            "Fri": "Пт", "Sat": "Сб", "Sun": "Вс"
        }
        date_str = local_dt.strftime('%d.%m (%a) %H:%M')
        for eng, rus in days_map.items():
            date_str = date_str.replace(eng, rus)
        return date_str
    else:
        return local_dt.strftime('%d.%m (%a) %H:%M')


async def get_group_game_number(session: AsyncSession, game: Game) -> int:
    """Returns 1-based sequential game number within its chat group."""
    if not game or not getattr(game, 'chat_id', None):
        return 1
    try:
        from sqlalchemy import func, or_
        chat_id_str = str(game.chat_id)
        alt_chat_id = int(chat_id_str.replace("-100", "-")) if "-100" in chat_id_str else int("-100" + chat_id_str.replace("-", ""))
        chat_ids = {game.chat_id, alt_chat_id, abs(game.chat_id), abs(alt_chat_id)}

        if getattr(game, 'channel_id', None):
            chan_str = str(game.channel_id)
            alt_chan = int(chan_str.replace("-100", "-")) if "-100" in chan_str else int("-100" + chan_str.replace("-", ""))
            chat_ids.update([game.channel_id, alt_chan, abs(game.channel_id), abs(alt_chan)])

        chat_cond = Game.chat_id.in_(chat_ids)
        if hasattr(Game, 'channel_id'):
            chat_cond = or_(chat_cond, Game.channel_id.in_(chat_ids))

        # Exclude cancelled games unless it's the queried game itself
        status_cond = or_(Game.status != GameStatus.CANCELLED, Game.id == game.id)

        res = await session.execute(
            select(func.count(Game.id)).where(
                chat_cond,
                status_cond,
                Game.id <= game.id
            )
        )
        val = res.scalar()
        if val is not None and val > 0:
            return val
        return 1
    except Exception:
        return 1


def _format_header_section(game, date_str: str, game_number: int = None, lang: str = "en") -> str:
    is_en = (lang or "en").lower() == "en"
    game_type_val = (game.game_type.value if hasattr(game.game_type, 'value') else str(game.game_type or "")).lower()
    is_draft = game_type_val == "draft"
    
    num_str = f"#{game_number}" if game_number is not None else f"#{game.id}"
    duration_val = f"{game.duration:g}" if game.duration else ""
    mpc = getattr(game, 'main_players_count', 22) or 22
    team_format = f"{mpc // 2}x{mpc // 2}"

    if is_en:
        type_label = "🎯 <b>Draft Match</b>" if is_draft else "🟢 <b>General Match</b>"
        duration_str = f" 🕒 {duration_val} hours" if duration_val else ""
        text = f"{type_label} <b>{num_str}</b>\n"
        text += f"⚽ <b>Format: {team_format}</b> ({game.max_players} players needed)\n"
        text += f"📅 <b>{date_str}{duration_str}</b>\n"
        text += f"📍 <b>{html.escape(game.location)}</b>\n"
    else:
        type_label = "🎯 <b>Драфт</b>" if is_draft else "🟢 <b>Общая игра</b>"
        duration_str = f" 🕒 {duration_val} часа" if duration_val else ""
        text = f"{type_label} <b>{num_str}</b>\n"
        text += f"⚽ <b>Формат: {team_format}</b> (нужно {game.max_players} человек)\n"
        text += f"📅 <b>{date_str}{duration_str}</b>\n"
        text += f"📍 <b>{html.escape(game.location)}</b>\n"
    return text


def _format_single_team(game, signups, team_enum, team_name, needed_gk, lang: str = "en") -> str:
    is_en = (lang or "en").lower() == "en"
    text = ""
    t_players = [
        (s, u) for (s, u) in signups 
        if s.status == SignupStatus.ACTIVE and s.team == team_enum
    ]
    text += f"{team_name} ({len(t_players)}):\n"
    
    groups = {"GK": [], "DEF": [], "MID": [], "FWD": []}
    for s, u in t_players:
        pos_enum = s.position if s.position else u.player_position
        pos_str = pos_enum.value if pos_enum else "DEF"
        if pos_str == "GK": groups["GK"].append((s, u))
        elif pos_str in ["CB", "LB", "RB", "LWB", "RWB"]: groups["DEF"].append((s, u))
        elif pos_str in ["CM", "CDM", "CAM", "LM", "RM"]: groups["MID"].append((s, u))
        elif pos_str in ["ST", "CF", "FWD", "LW", "RW"]: groups["FWD"].append((s, u))
        else: groups["DEF"].append((s, u))
    
    if is_en:
        headers = {"GK": "<b>Goalkeepers</b>", "DEF": "<b>Defenders</b>", "MID": "<b>Midfielders</b>", "FWD": "<b>Forwards</b>"}
        sub_marker = "   --- substitute ---\n"
        gk_field_marker = "<i>🧤 Goalkeeper decided on field</i>\n"
    else:
        headers = {"GK": "<b>Вратари</b>", "DEF": "<b>Защита</b>", "MID": "<b>Полузащита</b>", "FWD": "<b>Нападение</b>"}
        sub_marker = "   --- замена ---\n"
        gk_field_marker = "<i>🧤 Вратарь решается на поле</i>\n"

    team_counter = 1
    has_gk = False
    for cat in ["GK", "DEF", "MID", "FWD"]:
        plist = groups[cat]
        if not plist: continue
        text += f"<i>{headers[cat]}</i>\n"
        for signup, user in plist:
            if cat == "GK": has_gk = True
            text += f"{team_counter}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a> <i>{format_positions(user, signup)}</i>\n"
            m_per_team = (getattr(game, 'main_players_count', 22) or 22) // (game.team_count or 2)
            if team_counter == m_per_team:
                 text += sub_marker
            team_counter += 1
    
    if not has_gk and needed_gk:
         text += gk_field_marker
    text += "\n"
    return text


def _format_teams_section(game, signups, lang: str = "en") -> str:
    is_en = (lang or "en").lower() == "en"
    text = ""
    team_map = {0: Team.A, 1: Team.B, 2: Team.C}
    if is_en:
        team_names = ["🟠 Team A", "🟢 Team B", "🔵 Team C"]
        unassigned_title = "⚪ <b>Unassigned</b>"
    else:
        team_names = ["🟠 Команда А", "🟢 Команда Б", "🔵 Команда С"]
        unassigned_title = "⚪ <b>Нераспределенные</b>"

    team_gk_flags = [game.has_active_gk_a, game.has_active_gk_b, getattr(game, 'has_active_gk_c', True)] 
    count = game.team_count if game.team_count else 2
    
    for i in range(count):
        team_enum = team_map.get(i)
        if not team_enum: continue
        t_name = team_names[i] if i < len(team_names) else (f"Team {i+1}" if is_en else f"Команда {i+1}")
        needed_gk = team_gk_flags[i] if i < len(team_gk_flags) else True
        text += _format_single_team(game, signups, team_enum, t_name, needed_gk, lang=lang)
    
    unassigned = [s for s in signups if s[0].status == SignupStatus.ACTIVE and s[0].team is None]
    if unassigned:
        text += f"{unassigned_title} ({len(unassigned)}):\n"
        for i, (signup, user) in enumerate(unassigned, 1):
            text += f"{i}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a> <i>{format_positions(user, signup)}</i>\n"
    return text


def _format_players_section(game, active_players, lang: str = "en") -> str:
    is_en = (lang or "en").lower() == "en"
    limit = getattr(game, 'signup_limit', game.max_players) or game.max_players
    header = f"👥 <b>Players</b> ({len(active_players)}/{limit}):\n" if is_en else f"👥 <b>Игроки</b> ({len(active_players)}/{limit}):\n"
    text = header

    if active_players:
        for i, (signup, user) in enumerate(active_players, 1):
             text += f"{i}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a> <i>{format_positions(user, signup)}</i>\n"
    else:
        text += "\nNobody yet... 🦗\n" if is_en else "\nПока никого... 🦗\n"
    return text


def _format_reserve_section(reserve_players, lang: str = "en") -> str:
    is_en = (lang or "en").lower() == "en"
    text = ""
    if reserve_players:
        header = f"\n🕒 <b>Reserve</b> ({len(reserve_players)}):\n" if is_en else f"\n🕒 <b>Резерв</b> ({len(reserve_players)}):\n"
        text += header
        for i, (signup, user) in enumerate(reserve_players, 1):
            text += f"{i}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a> <i>{format_positions(user, signup)}</i>\n"
    return text


def _format_price_section(game, lang: str = "en") -> str:
    is_en = (lang or "en").lower() == "en"
    text = ""
    if game.price > 0:
        price_word = "Match fee" if is_en else "Взнос"
        currency = "CZK" if is_en else "крон"
        text += f"——————————————————\n"
        text += f"💰 <b>{price_word}:</b> {game.price} {currency}\n"
        if game.payment_info:
            text += f"💳 <code>{html.escape(game.payment_info)}</code>\n"
    return text


async def format_game_message(game: Game, session: AsyncSession, is_short: bool = False, signups: list = None, lang: str = None) -> str:
    """
    Generates the text for the Live Message.
    If is_short=True, returns a minimal version for group chats.
    Uses Chat.language or provided lang parameter (default 'en').
    """
    if lang is None:
        try:
            chat = await session.get(Chat, game.chat_id)
            if chat and chat.language:
                lang = chat.language.value if hasattr(chat.language, 'value') else str(chat.language)
            else:
                lang = "en"
        except Exception:
            lang = "en"
    lang = (lang or "en").lower()

    if signups is None:
        # Fetch signups with user data if not provided
        result = await session.execute(
            select(Signup, User)
            .join(User)
            .where(Signup.game_id == game.id)
            .order_by(Signup.created_at)
        )
        signups = result.all()

    active_players = [s for s in signups if s[0].status == SignupStatus.ACTIVE]
    reserve_players = [s for s in signups if s[0].status == SignupStatus.RESERVE]

    game_number = await get_group_game_number(session, game)
    date_str = _format_date(game.date_time, lang=lang)
    text = _format_header_section(game, date_str, game_number=game_number, lang=lang)
    
    is_en = (lang == "en")

    if is_short:
        text += f"——————————————————\n"
        players_lbl = "Players" if is_en else "Игроков"
        text += f"👥 <b>{players_lbl}:</b> {len(active_players)}/{game.max_players}\n"
        if reserve_players:
            res_lbl = "Reserve" if is_en else "В резерве"
            text += f"🕒 <b>{res_lbl}:</b> {len(reserve_players)}\n"
        
        # Add deep link to channel message if exists
        if game.channel_id and game.channel_message_id:
            hint = "Full roster in the channel" if is_en else "Полный список игроков в канале"
            text += f"\n👉 <i>{hint}</i>\n"
        
        return text

    # Full version below...
    text += f"——————————————————\n"
    
    # Check if teams are active (Active Game logic)
    show_teams = False
    if game.status in [GameStatus.ACTIVE, GameStatus.FINISHED]:
        show_teams = True

    if show_teams:
        text += _format_teams_section(game, signups, lang=lang)
    else:
        text += _format_players_section(game, active_players, lang=lang)

    text += _format_reserve_section(reserve_players, lang=lang)
    text += _format_price_section(game, lang=lang)

    return text


async def update_game_message(bot, game, session: AsyncSession):
    """
    Updates the live game message in both primary and channel chats.
    Supports minimal/full views and respects Chat.language.
    """
    from app.bot.keyboards import get_channel_game_keyboard
    from aiogram.exceptions import TelegramBadRequest
    import logging

    # Resolve Chat language
    lang = "en"
    try:
        chat = await session.get(Chat, game.chat_id)
        if chat and chat.language:
            lang = chat.language.value if hasattr(chat.language, 'value') else str(chat.language)
    except Exception:
        lang = "en"
    lang = (lang or "en").lower()
    
    # Fetch fresh signups from database
    result = await session.execute(
        select(Signup, User)
        .join(User)
        .where(Signup.game_id == game.id)
        .order_by(Signup.created_at)
    )
    signups = result.all()
    
    # 1. Update Channel (Full mode) if distinct from primary chat
    if game.channel_id and game.channel_message_id and (game.channel_id != game.chat_id or game.channel_message_id != game.message_id):
        text_full = await format_game_message(game, session, is_short=False, signups=signups, lang=lang)
        cta = "\n\n<b>Registration is open. Join in the chat!</b>" if lang == "en" else "\n\n<b>Запись открыта. Переходите в чат.</b>"
        text_full += cta
        
        # Add hidden deep link so Telegram channel discussion forward carries the start link
        from app.config import settings
        bot_username = settings.bot_username
        hidden_link = f'<a href="https://t.me/{bot_username}?start=game_{game.id}">&#8203;</a>'
        text_full = hidden_link + text_full
        
        try:
            await bot.edit_message_text(
                chat_id=game.channel_id,
                message_id=game.channel_message_id,
                text=text_full,
                reply_markup=get_channel_game_keyboard(game.id, lang=lang),
                parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            logging.warning(f"Failed to edit message in channel {game.channel_id} due to Telegram API error: {e}")
        except Exception as e:
            logging.error(f"Unexpected error when editing message in channel {game.channel_id}: {e}")

    # 2. Update Primary Chat (Full mode by default per user request)
    text_short = await format_game_message(game, session, is_short=False, signups=signups, lang=lang)
    kb = get_channel_game_keyboard(game.id, lang=lang)
    try:
        await bot.edit_message_text(
            chat_id=game.chat_id,
            message_id=game.message_id,
            text=text_short,
            reply_markup=kb,
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        logging.warning(f"Failed to edit message in chat {game.chat_id} due to Telegram API error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error when editing message in chat {game.chat_id}: {e}")

    # 3. Trigger Admin Dashboard Update
    try:
         from app.bot.admin_dashboard import update_dashboard_message
         await update_dashboard_message(bot, game.id, session)
    except (ImportError, Exception) as e:
         import logging
         logging.warning(f"Failed to update dashboard for game {game.id}: {e}")
