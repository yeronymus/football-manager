
from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.models import User, GameStats
from app.db.database import get_db

router = Router()

@router.message(Command("top"))
async def cmd_top(message: types.Message, command: CommandObject, session: AsyncSession):
    """
    Shows top lists.
    Usage: /top [category]
    Categories: rating (default), goals, mvp, matches
    """
    args = command.args.split() if command.args else []
    category = args[0].lower() if args else "rating"
    
    # Defaults
    limit = 10
    text = ""
    
    if category in ["rating", "elo", "рейтинг"]:
        stmt = select(User).order_by(desc(User.rating), desc(User.games_played)).limit(limit)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        text = "🏆 <b>Топ Рейтинг (ELO):</b>\n\n"
        for i, u in enumerate(users, 1):
            text += f"{i}. {u.full_name} — <b>{u.rating}</b> ({u.games_played} игр)\n"
            
    elif category in ["goals", "g", "голы"]:
        # Aggregate goals from GameStats
        stmt = (
            select(User.full_name, func.sum(GameStats.goals).label("total_goals"))
            .join(GameStats, User.user_id == GameStats.user_id)
            .group_by(User.user_id, User.full_name)
            .order_by(desc("total_goals"))
            .limit(limit)
        )
        result = await session.execute(stmt)
        data = result.all()
        
        text = "⚽ <b>Топ Бомбардиры:</b>\n\n"
        for i, (name, goals) in enumerate(data, 1):
            text += f"{i}. {name} — <b>{goals}</b>\n"
            
    elif category in ["mvp", "мвп"]:
        stmt = select(User).order_by(desc(User.stats_mvp), desc(User.games_played)).limit(limit)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        text = "🌟 <b>Топ MVP:</b>\n\n"
        for i, u in enumerate(users, 1):
            if u.stats_mvp > 0:
                text += f"{i}. {u.full_name} — <b>{u.stats_mvp}</b>\n"
        if not text.endswith("\n"): text += "Пока никого..."

    elif category in ["matches", "games", "матчи", "игры"]:
        stmt = select(User).order_by(desc(User.games_played), desc(User.rating)).limit(limit)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        text = "🏃 <b>Топ по играм:</b>\n\n"
        for i, u in enumerate(users, 1):
             text += f"{i}. {u.full_name} — <b>{u.games_played}</b>\n"

    else:
        text = (
            "Available categories:\n"
            "/top rating — ELO Rating\n"
            "/top goals — Goals Scored\n"
            "/top mvp — MVP Awards\n"
            "/top matches — Games Played"
        )
        
    await message.answer(text)
