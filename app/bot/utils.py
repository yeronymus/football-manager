from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Game, Signup, User, SignupStatus, Position, Team, GameStatus
import html

async def format_game_message(game: Game, session: AsyncSession) -> str:
    """
    Generates the text for the Live Message.
    """
    # Fetch signups with user data
    result = await session.execute(
        select(Signup, User)
        .join(User)
        .where(Signup.game_id == game.id)
        .order_by(Signup.created_at)
    )
    signups = result.all()

    active_players = [s for s in signups if s[0].status == SignupStatus.ACTIVE]
    reserve_players = [s for s in signups if s[0].status == SignupStatus.RESERVE]

    # Grouping removed (Unused and caused AttributeError)

    # Invisible link for deep linking
    text = f'<a href="https://t.me/fm_metabot?start=game_{game.id}">&#8203;</a>'
    
    # Localize Date (Assuming DB is UTC and user wants Prague CET +1)
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
    duration_str = f" 🕒 {game.duration} часа" if game.duration else ""
    text += f"⚽ <b>{date_str}{duration_str}</b>\n"
    text += f"📍 <b>{html.escape(game.location)}</b>\n"
    text += f"——————————————————\n"
    
    # Check if teams are active (Active Game logic)
    # Determine if we should show teams.
    # We show teams if ANY player has a team assigned? Or if status is ACTIVE?
    # Game Status is reliable.
    show_teams = False
    if game.status in [GameStatus.ACTIVE, GameStatus.FINISHED]:
        show_teams = True

    # Helper for formatting positions
    def format_positions(user, signup):
        # Override if Signup has a specific position set (Draft override)
        main_pos = signup.position.value if signup.position else user.player_position.value
        
        if user.alt_positions:
            return f"{main_pos} ({', '.join(user.alt_positions)})"
        return main_pos

    if show_teams:
        team_map = {0: Team.A, 1: Team.B, 2: Team.C}
        team_names = ["🟠 Команда А", "🟢 Команда Б", "🔵 Команда С"]
        team_gk_flags = [game.has_active_gk_a, game.has_active_gk_b, getattr(game, 'has_active_gk_c', True)] 
        
        # Iterate up to game.team_count (default 2 if None)
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
            
            # Grouping Logic
            groups = {
                "GK": [],
                "DEF": [],
                "MID": [],
                "FWD": []
            }
            
            for s, u in t_players:
                # Determine effective position
                pos_enum = s.position if s.position else u.player_position
                pos_str = pos_enum.value if pos_enum else "DEF"
                
                # Categorize
                if pos_str == "GK":
                    groups["GK"].append((s, u))
                elif pos_str in ["CB", "LB", "RB", "LWB", "RWB"]:
                    groups["DEF"].append((s, u))
                elif pos_str in ["CM", "CDM", "CAM", "LM", "RM"]:
                    groups["MID"].append((s, u))
                elif pos_str in ["ST", "CF", "FWD", "LW", "RW"]:
                    groups["FWD"].append((s, u))
                else:
                    groups["DEF"].append((s, u)) # Fallback
            
            # Headers
            headers = {
                "GK": "<b>Вратари</b>",
                "DEF": "<b>Защита</b>",
                "MID": "<b>Полузащита</b>",
                "FWD": "<b>Нападение</b>"
            }
            
            team_counter = 1
            has_gk = False
            
            # Render Order: GK -> DEF -> MID -> FWD
            for cat in ["GK", "DEF", "MID", "FWD"]:
                plist = groups[cat]
                if not plist: continue
                
                # Show Sub-Header for all categories
                text += f"<i>{headers[cat]}</i>\n"
                    
                for signup, user in plist:
                    if cat == "GK": has_gk = True
                    text += f"{team_counter}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a> <i>{format_positions(user, signup)}</i>\n"
                    team_counter += 1
            
            # Check GK Requirement
            needed_gk = team_gk_flags[i] if i < len(team_gk_flags) else True
            if not has_gk and needed_gk:
                 text += "<i>🧤 Вратарь решается на поле</i>\n"
            
            text += "\n"
        
        # Unassigned
        unassigned = [s for s in signups if s[0].status == SignupStatus.ACTIVE and s[0].team is None]
        if unassigned:
            text += f"⚪ <b>Нераспределенные</b> ({len(unassigned)}):\n"
            for i, (signup, user) in enumerate(unassigned, 1):
                text += f"{i}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a> <i>{format_positions(user, signup)}</i>\n"
            
    else:
        # Show Pool (Draft Mode) - Simplified List
        count = game.team_count if game.team_count else 2
        per_team = game.max_players // count
        fmt = " на ".join([str(per_team)] * count)
        
        text += f"👥 <b>Состав</b> ({len(active_players)}/{game.max_players}) ({fmt}):\n"

        if active_players:
            text += "\n🏃 <b>Игроки:</b>\n"
            for i, (signup, user) in enumerate(active_players, 1):
                 price_paid = "" # Future: if paid
                 text += f"{i}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a> <i>{format_positions(user, signup)}</i>{price_paid}\n"
        else:
            text += "\nПока никого... 🦗\n"
    if reserve_players:
        text += f"\n🕒 <b>Резерв</b> ({len(reserve_players)}):\n"
        for i, (signup, user) in enumerate(reserve_players, 1):
            text += f"{i}. <a href=\"tg://user?id={user.user_id}\">{html.escape(user.full_name)}</a>\n"
    
    # Payment info
    if game.price > 0:
        text += f"——————————————————\n"
        text += f"💰 <b>Цена:</b> {game.price} CZK\n"
        if game.payment_info:
            text += f"💳 <code>{html.escape(game.payment_info)}</code>\n"

    return text
