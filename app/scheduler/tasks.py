import asyncio
from app.bot.instance import bot
from app.db.database import async_session_maker
from app.db.models import Game, Signup, User, SignupStatus, GameStatus, Team
from sqlalchemy import select, func
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.config import settings

import logging
logger = logging.getLogger(__name__)

async def send_voting_message(game_id: int):
    async with async_session_maker() as session:
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        
        if not game:
            return

        # Get active players
        # Get active players with team info
        result = await session.execute(
            select(User, Signup.team)
            .join(Signup)
            .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
        )
        players_data = result.all()
        
        if not players_data:
            return

        team_a = []
        team_b = []
        
        for user, team in players_data:
            if team == Team.A:
                team_a.append(user)
            elif team == Team.B:
                team_b.append(user)

        # Create inline keyboard with players
        from app.bot.keyboards import get_voting_keyboard
        keyboard = get_voting_keyboard(game_id, team_a, team_b)
        
        # Delete old voting message if it exists
        if game.voting_message_id:
            try:
                await bot.delete_message(chat_id=game.chat_id, message_id=game.voting_message_id)
            except Exception as e:
                logger.warning(f"Failed to delete old voting message for game {game_id}: {e}")
        
        msg = await bot.send_message(
            chat_id=game.chat_id,
            text=f"Матч <b>#{game.id}</b> завершен.\n\n<b>Голосование за MVP открыто!</b>\nВыберите лучших игроков (по одному от команды), нажав на кнопки ниже.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        game.voting_message_id = msg.message_id
        await session.commit()

async def calculate_mvp(game_id: int):
    async with async_session_maker() as session:
        # Get game info
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        
        if not game:
            return

        # Silently edit old voting message to clean it up and remove keyboard
        if game.voting_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=game.chat_id,
                    message_id=game.voting_message_id,
                    text=f"Матч <b>#{game.id}</b> завершен.\n\n<b>Голосование за MVP закрыто!</b>",
                    reply_markup=None,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Failed to edit/close voting message for game {game_id}: {e}")


async def remind_admin_to_finish(game_id: int):
    async with async_session_maker() as session:
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
        web_app_url = f"{settings.webapp_url.rstrip('/')}/web/finish.html?id={game.id}"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Заполнить матч", web_app=types.WebAppInfo(url=web_app_url))]
        ])
        
        try:
            await bot.send_message(
                chat_id=creator_id,
                text=f"⏰ Матч <b>#{game.id}</b> уже должен закончиться.\n\nПожалуйста, внесите счет и авторов голов, чтобы обновить статистику!",
                reply_markup=kb,
                parse_mode="HTML"
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
    async with async_session_maker() as session:
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
                    # Promote from reserve
            reserves_result = await session.execute(
                select(Signup)
                .where(Signup.game_id == game_id, Signup.status == SignupStatus.RESERVE, Signup.user_id >= 0)
                .order_by(Signup.created_at) # FIFO
                .limit(slots_available)
            )
            promoted_signups = reserves_result.scalars().all()
            
            if promoted_signups:
                async def notify_user(signup):
                    try:
                        await bot.send_message(
                            signup.user_id, 
                            f"🧤 Бронь вратарей снята (24ч)!\nВы переведены в основной состав на матч #{game.id}!"
                        )
                    except Exception as e:
                        print(f"Failed to notify user {signup.user_id}: {e}")
                
                for signup in promoted_signups:
                    signup.status = SignupStatus.ACTIVE

                await asyncio.gather(*(notify_user(signup) for signup in promoted_signups))

                await session.commit()
                
                # Update Message
                from app.bot.utils import format_game_message
                
                text = await format_game_message(game, session)
                
                if game.message_id and game.chat_id:
                    from app.bot.keyboards import get_channel_game_keyboard
                    kb = get_channel_game_keyboard(game.id)
                    try:
                        await bot.edit_message_text(
                            chat_id=game.chat_id,
                            message_id=game.message_id,
                            text=text,
                            reply_markup=kb,
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                
                try:
                    from app.bot.admin_dashboard import update_dashboard_message
                    await update_dashboard_message(bot, game.id, session)
                except (ImportError, Exception) as e:
                    logger.warning(f"Failed to update dashboard: {e}")

async def publish_game_task(game_id: int):
    async with async_session_maker() as session:
        game = await session.get(Game, game_id)
        if not game:
            return

        from app.bot.utils import format_game_message
        from app.bot.keyboards import get_channel_game_keyboard
        
        # 1. Publish to Channel (Full)
        if game.channel_id:
            text_full = await format_game_message(game, session, is_short=False)
            
            # Add hidden deep link so Telegram channel discussion forward carries the start link
            from app.config import settings
            bot_username = settings.bot_username
            hidden_link = f'<a href="https://t.me/{bot_username}?start=game_{game.id}">&#8203;</a>'
            text_full = hidden_link + text_full
            
            try:
                sent_full = await bot.send_message(
                    chat_id=game.channel_id,
                    text=text_full,
                    reply_markup=get_channel_game_keyboard(game.id)
                )
                game.channel_message_id = sent_full.message_id
            except Exception as e:
                print(f"Failed to publish to channel {game.channel_id}: {e}")

        # 2. Publish to Group (Full mode per user request)
        text_short = await format_game_message(game, session, is_short=False)
        kb = get_channel_game_keyboard(game.id)
        try:
            sent_message = await bot.send_message(
                chat_id=game.chat_id,
                text=text_short,
                reply_markup=kb
            )
            
            game.message_id = sent_message.message_id
            await session.commit()
            
            try:
                await bot.pin_chat_message(chat_id=game.chat_id, message_id=sent_message.message_id)
            except: pass
            
        except Exception as e:
            print(f"Failed to publish game task {game.id} to chat: {e}")
