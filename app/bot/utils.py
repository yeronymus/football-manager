from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Game, Signup, User, SignupStatus, Position, Team, GameStatus
import html

async def format_game_message(game: Game, session: AsyncSession, is_short: bool = False, signups: list = None) -> str:
    """
    Generates the text for the Live Message.
    If is_short=True, returns a minimal version for group chats.
    """
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

    # Localize Date
    from datetime import timedelta
    local_dt = game.date_time + timedelta(hours=1)
    
    days_map = {
        "Mon": "Пн", "Tue": "Вт", "Wed": "Ср", "Thu": "Чт",
        "Fri": "Пт", "Sat": "Сб", "Sun": "Вс"
    }
    date_str = local_dt.strftime('%d.%m (%a) %H:%M')
    for eng, rus in days_map.items():
        date_str = date_str.replace(eng, rus)

    # Header
    # Hidden Link for Auto-Forward Detection (Zero-width space)
    # This allows common.py to detect the game_id in channel forwards
    hidden_link = f'<a href="https://t.me/fm_metabot?start=game_{game.id}">&#8203;</a>'
    
    # Game Type Label - handle both str and Enum
    game_type_val = (game.game_type.value if hasattr(game.game_type, 'value') else str(game.game_type or "")).lower()
    is_draft = game_type_val == "draft"
    type_label = "🎯 <b>Драфт</b>" if is_draft else "🟢 <b>Общая игра</b>"
    
    duration_val = f"{game.duration:g}" if game.duration else ""
    duration_str = f" 🕒 {duration_val} часа" if duration_val else ""
    text = f"{hidden_link}{type_label}\n"
    text += f"⚽ <b>{date_str}{duration_str}</b>\n"
    text += f"📍 <b>{html.escape(game.location)}</b>\n"
    
    if is_short:
        text += f"——————————————————\n"
        text += f"👥 <b>Игроков:</b> {len(active_players)}/{game.max_players}\n"
        if reserve_players:
            text += f"🕒 <b>В резерве:</b> {len(reserve_players)}\n"
        
        # Add deep link to channel message if exists
        if game.channel_id and game.channel_message_id:
            # Construct a private link if possible, or just a mention
            # Telegram channel links: https://t.me/c/CHANNEL_ID/MSG_ID (for private)
            # or https://t.me/CHANNEL_NAME/MSG_ID (for public)
            # Since we only have channel_id, we can't easily build a public link without name.
            # But we can provide a button instead.
            text += f"\n👉 <i>Полный список игроков в канале</i>\n"
        
        return text

    # Full version below...
    text += f"——————————————————\n"
    
    # Check if teams are active (Active Game logic)
    show_teams = False
    if game.status in [GameStatus.ACTIVE, GameStatus.FINISHED]:
        show_teams = True

    # Helper for formatting positions
    def format_positions(user, signup):
        main_pos = signup.position.value if signup.position else user.player_position.value
        if user.alt_positions:
            return f"{main_pos} ({', '.join(user.alt_positions)})"
        return main_pos

    if show_teams:
        team_map = {0: Team.A, 1: Team.B, 2: Team.C}
        team_names = ["🟠 Команда А", "🟢 Команда Б", "🔵 Команда С"]
        team_gk_flags = [game.has_active_gk_a, game.has_active_gk_b, getattr(game, 'has_active_gk_c', True)] 
        
        count = game.team_count if game.team_count else 2
        
        for i in range(count):
            team_enum = team_map.get(i)
            if not team_enum: continue
            
            t_players = [
                (s, u) for (s, u) in signups 
                if s.status == SignupStatus.ACTIVE and s.team == team_enum
            ]
            t_name = team_names[i] if i < len(team_names) else f"Команда {i+1}"
            text += f"{t_name} ({len(t_players)}):\n"
            
            groups = {"GK": [], "DEF": [], "MID": [], "FWD": []}
            for s, u in t_players:
                pos_enum = s.position if s.position else u.player_position
                pos_str = pos_enum.value if pos_enum else "DEF"
                if pos_str == "GK": groups["GK"].append((s, u))
                elif pos_str in ["CB", "LB", "RB", "LWB", "RWB"]: groups["DEF"].append((s, u))
                elif pos_str in ["CM", "CDM", "CAM", "LM", "RM"]: groups["MID"].append((s, u))
                elif pos_str in ["ST", "CF", "FWD", "LW", "RW"]: groups["FWD"].append((s, u))
                else: groups["DEF"].append((s, u))
            
            headers = {"GK": "<b>Вратари</b>", "DEF": "<b>Защита</b>", "MID": "<b>Полузащита</b>", "FWD": "<b>Нападение</b>"}
            team_counter = 1
            has_gk = False
            for cat in ["GK", "DEF", "MID", "FWD"]:
                plist = groups[cat]
                if not plist: continue
                text += f"<i>{headers[cat]}</i>\n"
                for signup, user in plist:
                    if cat == "GK": has_gk = True
                    text += f"{team_counter}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a> <i>{format_positions(user, signup)}</i>\n"
                    team_counter += 1
            
            needed_gk = team_gk_flags[i] if i < len(team_gk_flags) else True
            if not has_gk and needed_gk:
                 text += "<i>🧤 Вратарь решается на поле</i>\n"
            text += "\n"
        
        unassigned = [s for s in signups if s[0].status == SignupStatus.ACTIVE and s[0].team is None]
        if unassigned:
            text += f"⚪ <b>Нераспределенные</b> ({len(unassigned)}):\n"
            for i, (signup, user) in enumerate(unassigned, 1):
                text += f"{i}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a> <i>{format_positions(user, signup)}</i>\n"
    else:
        text += f"👥 <b>Состав</b> ({len(active_players)}/{game.max_players}):\n"

        if active_players:
            text += "\n🏃 <b>Игроки:</b>\n"
            for i, (signup, user) in enumerate(active_players, 1):
                 text += f"{i}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a> <i>{format_positions(user, signup)}</i>\n"
        else:
            text += "\nПока никого... 🦗\n"

    if reserve_players:
        text += f"\n🕒 <b>Резерв</b> ({len(reserve_players)}):\n"
        for i, (signup, user) in enumerate(reserve_players, 1):
            text += f"{i}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a>\n"
    
    if game.price > 0:
        text += f"——————————————————\n"
        text += f"💰 <b>Цена:</b> {game.price} CZK\n"
        if game.payment_info:
            text += f"💳 <code>{html.escape(game.payment_info)}</code>\n"

    return text

async def update_game_message(bot, game, session: AsyncSession):
    """
    Updates the live game message in both primary and channel chats.
    Now supports minimal view for primary chat.
    """
    from app.bot.keyboards import get_game_keyboard
    
    # Pre-fetch signups once for performance
    result = await session.execute(
        select(Signup, User)
        .join(User)
        .where(Signup.game_id == game.id)
        .order_by(Signup.created_at)
    )
    signups = result.all()
    
    # 1. Update Channel (Full mode)
    if game.channel_id and game.channel_message_id:
        text_full = await format_game_message(game, session, is_short=False, signups=signups)
        text_full += "\n\n<b>Запись открыта. Переходите в чат.</b>"
        try:
            await bot.edit_message_text(
                chat_id=game.channel_id,
                message_id=game.channel_message_id,
                text=text_full,
                reply_markup=None,
                parse_mode="HTML"
            )
        except Exception as e:
            import logging
            logging.warning(f"Failed to edit message in channel {game.channel_id}: {e}")


    # 2. Update Primary Chat (Short mode)
    text_short = await format_game_message(game, session, is_short=True, signups=signups)
    try:
        await bot.edit_message_text(
            chat_id=game.chat_id,
            message_id=game.message_id,
            text=text_short,
            reply_markup=get_game_keyboard(game.id),
            parse_mode="HTML"
        )
    except Exception as e:
        import logging
        logging.warning(f"Failed to edit message in chat {game.chat_id}: {e}")

    # 3. Trigger Admin Dashboard Update
    from app.bot.admin_dashboard import update_dashboard_message
    try:
         # Note: Dashboard currently does its own fetching to ensure freshness and different filtering
         await update_dashboard_message(bot, game.id, session)
    except Exception as e:
         import logging
         logging.warning(f"Failed to update dashboard for game {game.id}: {e}")
