from app.bot.main import bot
from app.db.database import get_session
from app.db.models import Game, Signup, User, Vote, SignupStatus, GameStatus, Team
from sqlalchemy import select, func
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.bot.elo import calculate_new_rating

async def send_voting_message(game_id: int):
    async for session in get_session():
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        
        if not game:
            return

        # Get active players
        result = await session.execute(
            select(User)
            .join(Signup)
            .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
        )
        players = result.scalars().all()
        
        if not players:
            return

        # Create keyboard with players
        buttons = []
        for player in players:
            buttons.append([InlineKeyboardButton(text=player.full_name, callback_data=f"vote_{game_id}_{player.user_id}")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await bot.send_message(
            chat_id=game.chat_id,
            text=f"Матч {game.location} завершен! Выберите MVP матча:",
            reply_markup=keyboard
        )
        
        # Schedule calculation in 2 hours
        from app.scheduler.main import scheduler
        from datetime import datetime, timedelta
        run_date = datetime.now() + timedelta(hours=2)
        scheduler.add_job(calculate_mvp, 'date', run_date=run_date, args=[game_id])

async def calculate_mvp(game_id: int):
    async for session in get_session():
        # Count votes
        result = await session.execute(
            select(Vote.target_id, func.count(Vote.id).label('count'))
            .where(Vote.game_id == game_id)
            .group_by(Vote.target_id)
            .order_by(func.count(Vote.id).desc())
            .limit(1)
        )
        winner_data = result.first()
        
        mvp_id = None
        votes_count = 0
        if winner_data:
            mvp_id, votes_count = winner_data
        
        # Get game info
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        
        if not game:
            return

        # Get MVP User
        mvp_user = None
        if mvp_id:
            result = await session.execute(select(User).where(User.user_id == mvp_id))
            mvp_user = result.scalar_one_or_none()
            if mvp_user:
                mvp_user.stats_mvp += 1

        # ELO Calculation
        if game.winner_team:
            # Fetch all active players with their teams
            result = await session.execute(
                select(User, Signup.team)
                .join(Signup)
                .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
            )
            players_data = result.all() # List of (User, Team)
            
            team_a_players = [p[0] for p in players_data if p[1] == Team.A]
            team_b_players = [p[0] for p in players_data if p[1] == Team.B]
            
            avg_a = sum(p.rating for p in team_a_players) / len(team_a_players) if team_a_players else 1200
            avg_b = sum(p.rating for p in team_b_players) / len(team_b_players) if team_b_players else 1200
            
            # Calculate for Team A
            actual_score_a = 1 if game.winner_team == Team.A else 0
            for player in team_a_players:
                is_mvp = (player.user_id == mvp_id)
                new_rating = calculate_new_rating(player, int(avg_b), actual_score_a, is_mvp)
                player.rating = new_rating
                player.games_played += 1
            
            # Calculate for Team B
            actual_score_b = 1 if game.winner_team == Team.B else 0
            for player in team_b_players:
                is_mvp = (player.user_id == mvp_id)
                new_rating = calculate_new_rating(player, int(avg_a), actual_score_b, is_mvp)
                player.rating = new_rating
                player.games_played += 1
                
            await session.commit()
            
        game.status = GameStatus.FINISHED
        await session.commit()
        
        text = f"🏆 MVP матча {game.location} признан {mvp_user.full_name} ({votes_count} голосов)!" if mvp_user else "MVP не выбран (нет голосов)."
        
        if game.winner_team:
            text += f"\n\n📈 Рейтинги обновлены! Победила команда {game.winner_team.value}."

        await bot.send_message(chat_id=game.chat_id, text=text)
