# from app.bot.main import bot  <-- REMOVED
from app.db.database import get_session
from app.db.models import Game, Signup, User, Vote, SignupStatus, GameStatus, Team, RatingHistory
from sqlalchemy import select, func
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.config import settings

async def send_voting_message(game_id: int):
    from app.bot.main import bot
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

        # Create keyboard with single WebApp button
        from app.config import settings
        vote_url = f"{settings.webapp_url}/web/vote.html?game_id={game_id}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🏆 Голосование (MVP)", web_app=types.WebAppInfo(url=vote_url))
        ]])
        
        await bot.send_message(
            chat_id=game.chat_id,
            text=f"Матч в <b>{game.location}</b> завершен.\n\n<b>Голосование за MVP открыто!</b>\nВыберите лучших игроков (по одному от команды) по кнопке ниже.\n<i>(Результаты через 5 часов)</i>\n\nП.С. Отправляйте свои голы @yeronym для внесения в статистику",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Schedule calculation in 5 hours
        from app.scheduler.main import scheduler
        from datetime import datetime, timedelta
        run_date = datetime.now() + timedelta(hours=5)
        scheduler.add_job(calculate_mvp, 'date', run_date=run_date, args=[game_id], id=f"mvp_calc_{game_id}", replace_existing=True)

async def calculate_mvp(game_id: int):
    from app.bot.main import bot
    async for session in get_session():
        # Get Team A Results
        res_a = await session.execute(
            select(User.full_name, func.count(Vote.id))
            .join(Vote, User.user_id == Vote.target_id)
            .where(Vote.game_id == game_id, Vote.vote_team == Team.A)
            .group_by(User.full_name)
            .order_by(func.count(Vote.id).desc())
        )
        results_a = res_a.all()
        
        # Get Team B Results
        res_b = await session.execute(
            select(User.full_name, func.count(Vote.id))
            .join(Vote, User.user_id == Vote.target_id)
            .where(Vote.game_id == game_id, Vote.vote_team == Team.B)
            .group_by(User.full_name)
            .order_by(func.count(Vote.id).desc())
        )
        results_b = res_b.all()
        
        # Get game info
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        
        if not game:
            return

        text = f"📊 <b>Результаты голосования MVP</b>\n\n"
        
        def format_results(items):
            if not items: return "<i>Голосов нет</i>"
            lines = []
            for i, (name, count) in enumerate(items):
                prefix = "🌟 " if i == 0 else "- "
                lines.append(f"{prefix}{name}: {count}")
            return "\n".join(lines)

        text += "<b>Команда А 🟠:</b>\n"
        text += format_results(results_a)
        text += "\n\n"
        
        text += "<b>Команда Б 🟢:</b>\n"
        text += format_results(results_b)

        await bot.send_message(chat_id=game.chat_id, text=text, parse_mode="HTML")

async def remind_admin_to_finish(game_id: int):
    from app.bot.main import bot
    async for session in get_session():
        # 1. Берем игру
        game = await session.get(Game, game_id)
        
        # Если игру уже закрыли - не беспокоим
        if not game or game.status == GameStatus.FINISHED:
            return

        # Double-check timing: If game was rescheduled, this old job might be firing prematurely.
        # Ensure now is actually past the reminder threshold (date_time + 2h).
        from datetime import datetime, timedelta
        # Ensure timezone awareness match
        now_tz = datetime.now(game.date_time.tzinfo) if game.date_time.tzinfo else datetime.now()
        threshold = game.date_time + timedelta(hours=1, minutes=59) # slightly lenient
        
        if now_tz < threshold:
             # This is an old job firing for a game that was moved to the future. Ignore.
             return

        # 2. Находим создателя игры (обычно он админ и был на поле)
        creator_id = game.created_by
        
        # 3. Формируем кнопку сразу на экран завершения
        web_app_url = f"{settings.webapp_url}/web/finish.html?id={game.id}"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Заполнить матч", web_app=types.WebAppInfo(url=web_app_url))]
        ])
        
        try:
            await bot.send_message(
                chat_id=creator_id,
                text=f"⏰ Матч в <b>{game.location}</b> уже должен закончиться.\n\nПожалуйста, внесите счет и авторов голов, чтобы обновить статистику!",
                reply_markup=kb
            )
        except Exception as e:
            # Админ мог заблочить бота
             print(f"Failed to remind admin: {e}")
async def release_gk_slots(game_id: int):
    """
    Called 48h after game creation.
    Releases the "GK Reservation" by auto-promoting players from the waiting list
    if there are still empty slots (which were effectively reserved).
    """
    async for session in get_session():
        game = await session.get(Game, game_id)
        if not game or game.status not in [GameStatus.OPEN, GameStatus.ACTIVE]:
            return

        # Count active
        result = await session.execute(
            select(func.count(Signup.id))
            .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
        )
        active_count = result.scalar()
        
        slots_available = game.max_players - active_count
        
        if slots_available > 0:
            from app.bot.main import bot
            # Promote from reserve
            reserves_result = await session.execute(
                select(Signup)
                .where(Signup.game_id == game_id, Signup.status == SignupStatus.RESERVE)
                .order_by(Signup.created_at) # FIFO
                .limit(slots_available)
            )
            promoted_signups = reserves_result.scalars().all()
            
            if promoted_signups:
                for signup in promoted_signups:
                    signup.status = SignupStatus.ACTIVE
                    
                    # Notify User
                    try:
                        await bot.send_message(
                            signup.user_id, 
                            f"🧤 Бронь вратарей снята (24ч)!\nВы переведены в основной состав на игру в {game.location}!"
                        )
                    except Exception as e:
                        print(f"Failed to notify user {signup.user_id}: {e}")
                
                await session.commit()
                
                # Update Message
                from app.bot.utils import format_game_message
                from app.bot.keyboards import get_game_keyboard
                from app.bot.admin_dashboard import update_dashboard_message
                
                text = await format_game_message(game, session)
                
                if game.message_id and game.chat_id:
                    try:
                        await bot.edit_message_text(
                            chat_id=game.chat_id,
                            message_id=game.message_id,
                            text=text,
                            reply_markup=get_game_keyboard(game.id),
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                
                await update_dashboard_message(bot, game.id, session)

async def publish_game_task(game_id: int):
    from app.bot.main import bot
    async for session in get_session():
        game = await session.get(Game, game_id)
        if not game:
            return

        from app.bot.utils import format_game_message
        from app.bot.keyboards import get_game_keyboard
        
        # 1. Publish to Channel (Full)
        if game.channel_id:
            text_full = await format_game_message(game, session, is_short=False)
            try:
                sent_full = await bot.send_message(
                    chat_id=game.channel_id,
                    text=text_full,
                    reply_markup=get_game_keyboard(game.id)
                )
                game.channel_message_id = sent_full.message_id
            except Exception as e:
                print(f"Failed to publish to channel {game.channel_id}: {e}")

        # 2. Publish to Group (Short)
        text_short = await format_game_message(game, session, is_short=True)
        try:
            sent_message = await bot.send_message(
                chat_id=game.chat_id,
                text=text_short,
                reply_markup=get_game_keyboard(game.id)
            )
            
            game.message_id = sent_message.message_id
            await session.commit()
            
            try:
                await bot.pin_chat_message(chat_id=game.chat_id, message_id=sent_message.message_id)
            except: pass
            
        except Exception as e:
            print(f"Failed to publish game task {game.id} to chat: {e}")
