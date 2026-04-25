
from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.models import User, GameStats, PlayerProfile
from app.core.repositories.user_repository import UserRepository

router = Router()

@router.message(Command("top"))
async def cmd_top(message: types.Message, command: CommandObject, session: AsyncSession):
    """
    Shows top lists.
    Usage: /top [category]
    Categories: rating (default), goals, mvp, matches
    Categories: rating (default), goals, mvp, matches
    """
    if message.chat.type == "private":
        await message.answer("🏆 Лидерборд теперь уникальный для каждой группы. Вызовите /top прямо в чате вашей группы или откройте Мини-Приложение.")
        return

    args = command.args.split() if command.args else []
    category = args[0].lower() if args else "rating"
    chat_id = message.chat.id
    
    limit = 10
    text = ""
    user_repo = UserRepository(session)
    
    if category in ["rating", "elo", "рейтинг"]:
        users_profiles = await user_repo.get_group_leaderboard(chat_id, limit, "rating")
        text = "🏆 <b>Топ Рейтинг (ELO) группы:</b>\n\n"
        for i, (u, p) in enumerate(users_profiles, 1):
            text += f"{i}. {u.full_name} — <b>{p.rating}</b> ({p.games_played} игр)\n"
            
    elif category in ["mvp", "мвп"]:
        users_profiles = await user_repo.get_group_leaderboard(chat_id, limit, "mvp")
        text = "🌟 <b>Топ MVP группы:</b>\n\n"
        for i, (u, p) in enumerate(users_profiles, 1):
            if p.stats_mvp > 0:
                text += f"{i}. {u.full_name} — <b>{p.stats_mvp}</b>\n"
        if "—" not in text: text += "Пока никого..."

    elif category in ["matches", "games", "матчи", "игры"]:
        users_profiles = await user_repo.get_group_leaderboard(chat_id, limit, "games")
        text = "🏃 <b>Топ по играм в группе:</b>\n\n"
        for i, (u, p) in enumerate(users_profiles, 1):
             text += f"{i}. {u.full_name} — <b>{p.games_played}</b>\n"

    elif category in ["goals", "g", "голы"]:
        # Aggregate goals for this group ONLY (joins Game and GameStats)
        from app.db.models import Game
        stmt = (
            select(User.full_name, func.sum(GameStats.goals).label("total_goals"))
            .join(GameStats, User.user_id == GameStats.user_id)
            .join(Game, Game.id == GameStats.game_id)
            .where(Game.chat_id == chat_id)
            .group_by(User.user_id, User.full_name)
            .order_by(desc("total_goals"))
            .limit(limit)
        )
        result = await session.execute(stmt)
        data = result.all()
        
        text = "⚽ <b>Топ Бомбардиры группы:</b>\n\n"
        for i, (name, goals) in enumerate(data, 1):
            if goals > 0:
                text += f"{i}. {name} — <b>{goals}</b>\n"
        if "—" not in text: text += "Пока никого..."

    else:
        text = (
            "Available categories:\n"
            "/top rating — ELO Rating\n"
            "/top goals — Goals Scored\n"
            "/top mvp — MVP Awards\n"
            "/top matches — Games Played"
        )
        
    await message.answer(text)
