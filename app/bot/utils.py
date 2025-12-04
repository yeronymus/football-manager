from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Game, Signup, User, SignupStatus, Position

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
    gk = [s for s in active_players if s[1].position == Position.GK]
    defenders = [s for s in active_players if s[1].position == Position.DEF]
    midfielders = [s for s in active_players if s[1].position == Position.MID]
    forwards = [s for s in active_players if s[1].position == Position.FWD]

    text = f"⚽ <b>Футбол: {game.location}</b>\n"
    text += f"📅 <b>{game.date_time.strftime('%d.%m (%a) %H:%M')}</b>\n\n"
    
    text += f"Состав ({len(active_players)}/{game.max_players}):\n\n"

    if gk:
        text += "🧤 <b>Вратари:</b>\n"
        for i, (signup, user) in enumerate(gk, 1):
            text += f"{i}. {user.full_name}\n"
        text += "\n"
    else:
        text += "🧤 <b>Вратари:</b> По очереди / Решим на поле\n\n"

    field_players = defenders + midfielders + forwards
    if field_players:
        text += "🏃 <b>Полевые:</b>\n"
        for i, (signup, user) in enumerate(field_players, 1):
            text += f"{i}. {user.full_name} ({user.position.value})\n"
    
    if reserve_players:
        text += "\n🕒 <b>Резерв:</b>\n"
        for i, (signup, user) in enumerate(reserve_players, 1):
            text += f"{i}. {user.full_name}\n"

    return text
