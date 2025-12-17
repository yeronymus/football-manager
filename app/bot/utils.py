from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Game, Signup, User, SignupStatus, Position, Team
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

    # Group by position
    gk = [s for s in active_players if s[1].player_position == Position.GK]
    defenders = [s for s in active_players if s[1].player_position == Position.DEF]
    midfielders = [s for s in active_players if s[1].player_position == Position.MID]
    forwards = [s for s in active_players if s[1].player_position == Position.FWD]

    # Invisible link for deep linking
    text = f'<a href="https://t.me/fm_metabot?start=game_{game.id}">&#8203;</a>'
    
    # Header
    text += f"⚽ <b>{html.escape(game.location)}</b>\n"
    text += f"📅 <b>{game.date_time.strftime('%d.%m (%a) %H:%M')}</b>\n"
    text += f"——————————————————\n"
    
    # Check if teams are active (Active Game logic)
    team_a = [s for s in signups if s[0].status == SignupStatus.ACTIVE and s[0].team == Team.A]
    team_b = [s for s in signups if s[0].status == SignupStatus.ACTIVE and s[0].team == Team.B]
    unassigned = [s for s in signups if s[0].status == SignupStatus.ACTIVE and s[0].team is None]
    
    has_teams = bool(team_a or team_b)
    
    if has_teams:
        # Show Teams
        text += f"🔴 <b>Команда А</b> ({len(team_a)}):\n"
        for i, (signup, user) in enumerate(team_a, 1):
            text += f"{i}. {html.escape(user.full_name)} <i>({user.player_position.value})</i>\n"
            
        text += f"\n🔵 <b>Команда B</b> ({len(team_b)}):\n"
        for i, (signup, user) in enumerate(team_b, 1):
            text += f"{i}. {html.escape(user.full_name)} <i>({user.player_position.value})</i>\n"
            
        if unassigned:
            text += f"\n⚪ <b>Нераспределенные</b> ({len(unassigned)}):\n"
            for i, (signup, user) in enumerate(unassigned, 1):
                text += f"{i}. {html.escape(user.full_name)} <i>({user.player_position.value})</i>\n"
            
    else:
        # Show Pool (Draft Mode)
        text += f"👥 <b>Состав</b> ({len(active_players)}/{game.max_players}):\n"

        if gk:
            text += "\n🧤 <b>Вратари:</b>\n"
            for i, (signup, user) in enumerate(gk, 1):
                text += f"• {html.escape(user.full_name)}\n"
        
        field_players = defenders + midfielders + forwards
        if field_players:
            text += "\n🏃 <b>Полевые:</b>\n"
            for i, (signup, user) in enumerate(field_players, 1):
                text += f"{i}. {html.escape(user.full_name)} <i>({user.player_position.value})</i>\n"
                
        if not gk and not field_players:
            text += "\nПока никого... 🦗\n"
    
    if reserve_players:
        text += f"\n🕒 <b>Резерв</b> ({len(reserve_players)}):\n"
        for i, (signup, user) in enumerate(reserve_players, 1):
            text += f"{i}. {html.escape(user.full_name)}\n"

    return text
