from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.models import Game, Chat, User, Signup, SignupStatus, GameStatus, Team, Vote
from app.api.schemas import GameCreate, GameFinishRequest, GameUpdate
from datetime import datetime, timedelta
import logging

# Scheduler imports (Lazy import inside methods often better to avoid circular, but here ok)
from app.scheduler.main import scheduler
from app.scheduler.tasks import send_voting_message, release_gk_slots, remind_admin_to_finish, publish_game_task
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard
from app.db.models import RatingHistory, GameStats


import logging

logger = logging.getLogger(__name__)

class GameActionError(Exception):
    """Base exception for game actions."""
    pass

class GameFullError(GameActionError):
    pass

class AlreadySignedUpError(GameActionError):
    pass

class CancellationLockedError(GameActionError):
    pass

class GameService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_game(self, game_id: int) -> Game | None:
        """Fetch game by ID."""
        return await self.session.get(Game, game_id)

    async def join_game(self, game_id: int, user_id: int) -> tuple[Signup, str]:
        """
        Registers a user for a game.
        Returns (Signup, alert_message).
        """
        # Lock the game row for update to handle race conditions
        result = await self.session.execute(
            select(Game).where(Game.id == game_id).with_for_update()
        )
        game = result.scalar_one_or_none()

        if not game or (game.status != GameStatus.OPEN and game.status != GameStatus.ACTIVE):
            raise GameActionError("Запись закрыта!")

        # Check if already signed up
        result = await self.session.execute(select(Signup).where(Signup.game_id == game_id, Signup.user_id == user_id))
        existing_signup = result.scalar_one_or_none()
        
        if existing_signup:
            raise AlreadySignedUpError("Вы уже записаны!")

        # Check for Past Game
        if game.date_time:
             now_tz = datetime.now(game.date_time.tzinfo)
             if game.date_time < now_tz:
                 raise GameActionError("Игра уже прошла!")

        # Fetch User for position check
        user = await self.session.get(User, user_id)
        if not user:
             raise GameActionError("Пользователь не найден. Пожалуйста, зарегистрируйтесь снова.")

        # Count current active signups
        result = await self.session.execute(select(func.count(Signup.id)).where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE))
        active_count = result.scalar()

        # --- 48h GK Priority Rule ---
        from app.db.models import Position
        
        status = SignupStatus.ACTIVE
        alert_msg = None
        
        is_gk_priority = False
        if game.created_at:
            # Assuming created_at is aware
            current_time = datetime.now(game.created_at.tzinfo)
            age_hours = (current_time - game.created_at).total_seconds() / 3600
            
            if age_hours < game.gk_hours: # Use dynamic gk_hours
                 # If user is NOT GK
                 if user.player_position != Position.GK:
                     # Check if we are encroaching on last 2 slots
                     slots_left = game.max_players - active_count
                     if slots_left <= 2:
                         # Force to Reserve
                         is_gk_priority = True
                         
        if is_gk_priority:
            status = SignupStatus.RESERVE
            alert_msg = f"🧤 Места зарезервированы для вратарей ({game.gk_hours}ч)! Вы в резерве."
        elif active_count >= game.max_players:
            status = SignupStatus.RESERVE
            alert_msg = "Резерв (мест нет)"
        else:
            status = SignupStatus.ACTIVE
        
        new_signup = Signup(game_id=game_id, user_id=user_id, status=status)
        self.session.add(new_signup)
        await self.session.commit()
        
        return new_signup, alert_msg

    async def leave_game(self, game_id: int, user_id: int, is_admin: bool = False) -> tuple[Game, bool]:
        """
        Unregisters a user.
        Returns (Game, was_active).
        """
        result = await self.session.execute(select(Signup).where(Signup.game_id == game_id, Signup.user_id == user_id))
        signup = result.scalar_one_or_none()
        
        if not signup:
            raise GameActionError(f"Вы не записаны на игру #{game_id}.")
 
        # Check Game exists
        game_result = await self.session.execute(select(Game).where(Game.id == game_id))
        game = game_result.scalar_one_or_none()
        
        if not game:
             raise GameActionError("Игра не найдена.")
 
        # --- 36h Cancellation Lock ---
        if game.date_time and not is_admin:
             current_time = datetime.now(game.date_time.tzinfo)
             time_diff = game.date_time - current_time
        
             if time_diff.total_seconds() < 36 * 3600:
                 raise CancellationLockedError("Слишком поздно выписываться, напиши админам")

        was_active = signup.status == SignupStatus.ACTIVE
        await self.session.delete(signup)
        
        # Auto-promotion logic
        if was_active and game.status == GameStatus.OPEN:
            # Check GK Reservation Window
            is_gk_priority_window = False
            if game.created_at:
                now_tz = datetime.now(game.created_at.tzinfo) if game.created_at.tzinfo else datetime.now()
                age_hours = (now_tz - game.created_at).total_seconds() / 3600
                if age_hours < game.gk_hours:
                    is_gk_priority_window = True

            # Get new active count
            res = await self.session.execute(
                select(func.count(Signup.id))
                .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
            )
            new_active_count = res.scalar()

            # Find first reserve with user data to check position
            from app.db.models import Position # Local import for safety
            reserve_result = await self.session.execute(
                select(Signup, User)
                .join(User)
                .where(Signup.game_id == game_id, Signup.status == SignupStatus.RESERVE)
                .order_by(Signup.created_at)
                .limit(1)
            )
            res_data = reserve_result.first()
            
            if res_data:
                first_reserve, res_user = res_data
                
                # Decision: Can we promote this person?
                can_promote = True
                
                if is_gk_priority_window:
                    # If this person is NOT a GK, check if we have "non-reserved" slots
                    if res_user.player_position != Position.GK:
                        # We have 2 slots reserved. Soft cap is max - 2.
                        if new_active_count >= (game.max_players - 2):
                            can_promote = False
                            logger.info(f"Skipping auto-promotion for non-GK {res_user.user_id} due to GK priority.")
                
                if can_promote:
                    first_reserve.status = SignupStatus.ACTIVE
                    logger.info(f"Auto-promoted user {res_user.user_id} to game {game_id}")

        await self.session.commit()
        return game, was_active

    async def create_game(self, game_data: GameCreate, creator_id: int) -> Game:
        """
        Creates a game, registers the chat if needed, handles auto-joins, 
        and schedules all necessary tasks (Publish, Voting, Reminders).
        """
        # 1. Ensure Chat Exists
        # Ideally this should be in ChatService, but simple enough here.
        chat = await self.session.get(Chat, game_data.chat_id)
        if not chat:
            try:
                from app.bot.main import bot
                chat_obj = await bot.get_chat(game_data.chat_id)
                chat = Chat(chat_id=game_data.chat_id, title=chat_obj.title or "Unknown Chat")
                self.session.add(chat)
                await self.session.commit()
            except Exception as e:
                logger.error(f"Chat not found: {e}")
                raise ValueError("Chat not found")

        # 2. Create Game Object
        new_game = Game(
            chat_id=game_data.chat_id,
            created_by=creator_id,
            date_time=game_data.date_time,
            location=game_data.location,
            max_players=game_data.max_players,
            price=game_data.price,
            payment_info=game_data.payment_info,
            team_count=game_data.team_count,
            gk_hours=game_data.gk_hours,
            duration=game_data.duration
        )
        self.session.add(new_game)
        await self.session.commit()
        await self.session.refresh(new_game)

        # 3. Auto-Join Admins
        # Dependency on UserService or raw DB calls?
        # Let's use raw DB for speed/simplicity within this transaction context, 
        # but cleaner to use UserService if we had DI. 
        # For now, sticking to logic similar to endpoint but cleaner.
        if game_data.auto_join_ids:
            for admin_id in game_data.auto_join_ids:
                # Ensure user logic handled by Caller? 
                # Endpoint handles User creation for admins. 
                # Let's assume users exist or handle safely.
                # Logic copied from endpoints but we assume users exist or created by calling code.
                # Actually, endpoints created them. We will keep that external or move here?
                # Moving complex "create user if not exists" loop here might be too much coupling.
                # Let's assume endpoints/caller ensures users exist.
                
                # Check overlap
                exists = await self.session.execute(select(Signup).where(Signup.game_id == new_game.id, Signup.user_id == admin_id))
                if not exists.scalar_one_or_none():
                     signup = Signup(game_id=new_game.id, user_id=admin_id, status=SignupStatus.ACTIVE)
                     self.session.add(signup)
            
            await self.session.commit()

        # 4. Scheduling Tasks
        should_publish_now = True
        
        # Check for Past/Retroactive Game
        now_tz = datetime.now(new_game.date_time.tzinfo) if new_game.date_time.tzinfo else datetime.now()
        is_past = new_game.date_time < now_tz
        
        logger.info(f"Creating Game: {new_game.date_time} (TZ: {new_game.date_time.tzinfo}) vs Now: {now_tz}")
        logger.info(f"Is Past: {is_past}")

        if is_past:
            should_publish_now = False # Silent mode for past games
            
        elif game_data.publish_at:
            if game_data.publish_at > now_tz:
                should_publish_now = False
                scheduler.add_job(publish_game_task, 'date', run_date=game_data.publish_at, args=[new_game.id])
        
        if should_publish_now:
            await self._publish_game_message(new_game)

        # Dashboard Update
        from app.bot.admin_dashboard import update_dashboard_message
        try:
             from app.bot.main import bot
             success = await update_dashboard_message(bot, new_game.id, self.session)
             if not success:
                 # Notify creator that no dashboard was sent
                 await bot.send_message(creator_id, f"⚠️ Игра создана, но <b>Admin Dashboard</b> не был отправлен. Похоже, чат этой игры не привязан к вашей личке. Используйте <code>/setup</code> в личке бота для настройки.")
        except Exception as e:
             logger.warning(f"Failed to send admin dashboard: {e}")

        # Schedule other lifecycle events
        # Safeguard: Don't schedule past events (Retroactive games)
        now_tz = datetime.now(new_game.date_time.tzinfo) if new_game.date_time.tzinfo else datetime.now()
        
        voting_time = new_game.date_time + timedelta(hours=2, minutes=30)
        if voting_time > now_tz:
            scheduler.add_job(send_voting_message, 'date', run_date=voting_time, args=[new_game.id], id=f"voting_{new_game.id}", replace_existing=True)
        
        # Reminder: 5h after voting opens (2.5 + 5 = 7.5h from start)
        reminder_time = new_game.date_time + timedelta(hours=7, minutes=30)
        if reminder_time > now_tz:
             scheduler.add_job(remind_admin_to_finish, 'date', run_date=reminder_time, args=[new_game.id], id=f"reminder_{new_game.id}", replace_existing=True)
        
        # GK Slots Release - Only if gk_hours > 0
        if new_game.gk_hours > 0:
            gk_release_time = new_game.created_at + timedelta(hours=new_game.gk_hours)
            # created_at might be None in object before refresh? No, refreshed above.
            if gk_release_time > now_tz:
                scheduler.add_job(release_gk_slots, 'date', run_date=gk_release_time, args=[new_game.id])

        await self.session.refresh(new_game) # Ensure all fields loaded for response
        return new_game

    async def update_game(self, data: GameUpdate) -> Game:
        """
        Updates game details.
        """
        game = await self.get_game(data.game_id)
        if not game:
            raise ValueError("Game not found")
        
        # Track changes for notification
        changes = []
        if data.location and data.location != game.location:
             changes.append(f"📍 Локация: {game.location} -> {data.location}")
             game.location = data.location
             
        if data.date_time:
             # Ensure both are compared fairly (aware vs aware)
             # SQLAlchemy usually returns aware if timezone=True
             if game.date_time != data.date_time:
                 old_str = game.date_time.strftime('%d.%m %H:%M')
                 new_str = data.date_time.strftime('%d.%m %H:%M')
                 if old_str != new_str:
                     changes.append(f"📅 Дата: {old_str} -> {new_str}")
                 game.date_time = data.date_time
                 
                 # --- Reschedule Tasks ---
                 try:
                     # Remove old jobs (best effort, as we don't track job IDs perfectly yet)
                     # But we can add new ones. Overlapping jobs might be an issue?
                     # Ideally we should store job IDs.
                     # For now, let's just ADD new jobs. The old ones will fire but we check 'game.status' inside them.
                     # wait, remind_admin checks if status is FINISHED. It doesn't check if time implies it should NOT fire yet.
                     # So we MUST try to remove or at least accept duplicates?
                     # Actually, if we add new jobs, we get double notifications.
                     # Let's rely on the fact that 'apscheduler' doesn't easily support 'remove by args' without IDs.
                     # So we just add new ones. The old one triggers -> checks DB -> sends message.
                     # If the old time is NOW, it sends "Match should be finished". 
                     # If we moved it to FUTURE, the old job still fires AT OLD TIME.
                     # Inside 'remind_admin_to_finish', we should check: is current_time >= game.date_time + 2h?
                     # If we moved game to future, 'remind_admin' logic should fail that check.
                     pass 
                     
                     from app.scheduler.tasks import send_voting_message, remind_admin_to_finish
                     from app.scheduler.main import scheduler
                     
                     now_tz = datetime.now(game.date_time.tzinfo)
                     
                     voting_time = game.date_time + timedelta(hours=2, minutes=30)
                     if voting_time > now_tz:
                         scheduler.add_job(send_voting_message, 'date', run_date=voting_time, args=[game.id], id=f"voting_{game.id}", replace_existing=True)
                     
                     reminder_time = game.date_time + timedelta(hours=7, minutes=30)
                     if reminder_time > now_tz:
                          scheduler.add_job(remind_admin_to_finish, 'date', run_date=reminder_time, args=[game.id], id=f"reminder_{game.id}", replace_existing=True)

                 except Exception as e:
                     logger.warning(f"Failed to reschedule tasks: {e}")
             
        if data.max_players and data.max_players != game.max_players:
             changes.append(f"👥 Мест: {game.max_players} -> {data.max_players}")
             game.max_players = data.max_players
             
        if data.price is not None and data.price != game.price:
             changes.append(f"💰 Цена: {game.price} -> {data.price}")
             game.price = data.price

        if data.payment_info and data.payment_info != game.payment_info:
             game.payment_info = data.payment_info
             
        if data.gk_hours is not None and data.gk_hours != game.gk_hours:
             game.gk_hours = data.gk_hours
             
        if data.duration is not None and data.duration != game.duration:
             game.duration = data.duration
             
        await self.session.commit()
        
        if changes:
             from app.bot.main import bot
             try:
                # Also update messages (Primary & Channel)
                public_text = await format_game_message(game, self.session)
                kb = get_game_keyboard(game.id)
                
                async def safe_edit(chat_id, msg_id):
                    if not chat_id or not msg_id: return
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=msg_id,
                            text=public_text,
                            reply_markup=kb,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                         logger.warning(f"Failed to edit msg in {chat_id}: {e}")

                await safe_edit(game.chat_id, game.message_id)
                await safe_edit(game.channel_id, game.channel_message_id)
             except Exception as e:
                 logger.warning(f"Failed to notify update: {e}")
                 
        await self.session.refresh(game)
        return game

    async def _publish_game_message(self, game: Game):
        """Internal helper to send/pin the game message."""
        from app.bot.main import bot
        if game.message_id:
            logger.info(f"Game {game.id} already published.")
            return

        message_text = await format_game_message(game, self.session)
        try:
            sent_message = await bot.send_message(
                chat_id=game.chat_id,
                text=message_text,
                reply_markup=get_game_keyboard(game.id)
            )
            
            game.message_id = sent_message.message_id
            await self.session.commit()
        except Exception as e:
            logger.warning(f"Failed to publish game message: {e}")

    async def balance_teams(self, game_id: int):
        """
        Balances teams, saves to DB, and notifies chat.
        """
        from app.bot.balancer import balance_teams as run_balance_teams, Player
        
        # Fetch game
        game = await self.get_game(game_id)
        if not game:
            raise ValueError("Game not found")
            
        # Fetch active signups
        result = await self.session.execute(
            select(User)
            .join(Signup)
            .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
        )
        players = result.scalars().all()
        
        if len(players) < 1:
            raise ValueError("Not enough players to balance")

        # Wrap User objects
        wrapped_players = [Player(p) for p in players]
        teams = run_balance_teams(wrapped_players, team_count=game.team_count)

        # Update DB
        team_map = {0: Team.A, 1: Team.B, 2: Team.C}
        
        for i, team_players in enumerate(teams):
            team_enum = team_map.get(i)
            if not team_enum: continue
                 
            for player in team_players:
                signup = (await self.session.execute(select(Signup).where(Signup.game_id == game_id, Signup.user_id == player.id))).scalar_one()
                signup.team = team_enum

        await self.session.commit()

        # Build Message
        from app.config import settings
        text = f"⚖️ <b>Составы команд ({game.location}):</b>\n\n"
        team_names = ["🟠 Команда А", "🟢 Команда Б", "🔵 Команда С"]
        
        for i, team_players in enumerate(teams):
            t_name = team_names[i] if i < len(team_names) else f"Команда {i+1}"
            text += f"<b>{t_name}:</b>\n"
            for p in team_players:
                rating_info = f" ({p.rating})" if settings.show_rating else ""
                pos_info = f" <i>{p.position}</i>"
                text += f"- {p.name}{pos_info}{rating_info}\n"
            text += "\n"
            
        if settings.show_rating:
            avgs = []
            for team_players in teams:
                avg = sum(p.rating for p in team_players) / len(team_players) if team_players else 0
                avgs.append(int(avg))
            text += f"\n📊 Средний рейтинг: {' vs '.join(map(str, avgs))}"

        # Instead of sending a new message, we update the main message with the teams
        # Actually, it's better to show teams in the main message ALWAYS if they exist.
        # But for now, let's just update the message text.
        try:
            public_text = await format_game_message(game, self.session)
            kb = get_game_keyboard(game.id)
            
            async def safe_edit(chat_id, msg_id):
                if not chat_id or not msg_id: return
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text=public_text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Failed to edit message in {chat_id}: {e}")

            await safe_edit(game.chat_id, game.message_id)
            await safe_edit(game.channel_id, game.channel_message_id)
        except Exception as e:
            logger.warning(f"Failed to update message after balance: {e}")
            
        return {"status": "balanced"}
        

    async def finish_game(self, data: GameFinishRequest) -> Game:
        """
        Finishes the game, saves scores/stats, calculates ELO, and notifies chat.
        """
        from app.bot.elo import calculate_new_rating
        
        # Fetch game
        game = await self.get_game(data.game_id)
        if not game:
             raise ValueError("Game not found")
        
        # Update game score and status
        if game.status == GameStatus.FINISHED:
            # Rollback previous results to allow editing/correction
            
            # 1. Revert Ratings & Games Played
            history_result = await self.session.execute(select(RatingHistory).where(RatingHistory.game_id == game.id))
            histories = history_result.scalars().all()
            for h in histories:
                user = await self.session.get(User, h.user_id)
                if user and h.old_rating is not None:
                    # We revert to old_rating. 
                    # Note: If multiple updates happened, order matters? 
                    # If we delete ALL history for this game, we effectively revert the chain steps.
                    # E.g. 100->105 (H1), 105->110 (H2).
                    # Loop H2: user=105. Loop H1: user=100. Correct.
                    user.rating = h.old_rating
                    user.games_played = max(0, user.games_played - 1)
                await self.session.delete(h)
                
            # 2. Revert Stats (MVP)
            stats_result = await self.session.execute(select(GameStats).where(GameStats.game_id == game.id))
            stats = stats_result.scalars().all()
            for s in stats:
                if s.is_mvp:
                    user = await self.session.get(User, s.user_id)
                    if user:
                        user.stats_mvp = max(0, user.stats_mvp - 1)
                await self.session.delete(s)
            
            await self.session.flush()

        # Update scores and status
        game.score_a = data.score_a
        game.score_b = data.score_b
        game.winner_team = data.winner_team
        game.status = GameStatus.FINISHED

        # MVP Logic: Driven ONLY by Manual Input (data.mvp_user_id)
        # Voting is advisory and announced in chat separately.
        mvp_ids = set()
        if data.mvp_user_id:
            mvp_ids.add(data.mvp_user_id)
        if data.mvp_team_a:
            mvp_ids.add(data.mvp_team_a)
        if data.mvp_team_b:
            mvp_ids.add(data.mvp_team_b)

        # Save player stats
        processed_stats_ids = set()
        for p_stat in data.player_stats:
            is_mvp = (p_stat.user_id in mvp_ids)
            if p_stat.goals > 0 or is_mvp:
                stat = GameStats(
                    game_id=game.id, 
                    user_id=p_stat.user_id, 
                    goals=p_stat.goals,
                    is_mvp=is_mvp
                )
                self.session.add(stat)
                processed_stats_ids.add(p_stat.user_id)
                
                # Update User Total MVP count
                if is_mvp:
                    user_obj = await self.session.get(User, p_stat.user_id)
                    if user_obj:
                         user_obj.stats_mvp += 1
        
        # Ensure MVPs without goals are recorded
        for mid in mvp_ids:
            if mid not in processed_stats_ids:
                stat = GameStats(game_id=game.id, user_id=mid, goals=0, is_mvp=True)
                self.session.add(stat)
                user_obj = await self.session.get(User, mid)
                if user_obj:
                     user_obj.stats_mvp += 1

        # ELO Calculation
        # Determine Ranks for 3-team games
        ranking = []
        if game.team_count == 3:
            scores = [
                (Team.A, game.score_a or 0),
                (Team.B, game.score_b or 0),
                (Team.C, game.score_c or 0)
            ]
            scores.sort(key=lambda x: x[1], reverse=True)
            ranking = [s[0] for s in scores] # [1st, 2nd, 3rd]

        # Fetch all active players with their teams
        result = await self.session.execute(
            select(User, Signup.team)
            .join(Signup)
            .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
        )
        players_data = result.all() # List of (User, Team)
        
        from app.db.models import RatingHistory

        for user, team in players_data:
            old_rating = user.rating
            change = -5 # Default
            
            if game.team_count == 2:
                if team == game.winner_team:
                    change = 10
                else:
                    change = -5
            else:
                # 3 Teams logic: 1st:+10, 2nd:0, 3rd:-5
                if team == ranking[0]:
                    change = 10
                elif team == ranking[1]:
                    change = 0
                else:
                    change = -5
            
            is_mvp = (user.user_id in mvp_ids)
            if is_mvp:
                change += 5
            
            user.rating += change
            user.games_played += 1
            user.stats_matches += 1
            
            # Record History
            self.session.add(RatingHistory(
                user_id=user.user_id,
                game_id=game.id,
                old_rating=old_rating,
                new_rating=user.rating,
                change=change
            ))

        await self.session.commit()
        
        # Notify chat
        from app.config import settings
        text = f"🏁 <b>Матч завершен!</b>\n\n"
        text += f"Команда оранжевые 🟠 {game.score_a}:{game.score_b} 🟢 Команда зеленые\n"
        
        # MVP
        if mvp_ids:
             text += "🌟 <b>MVP:</b> "
             mvp_names = []
             for mid in mvp_ids:
                 u = await self.session.get(User, mid)
                 if u: mvp_names.append(u.full_name)
             text += ", ".join(mvp_names) + "\n"
        
        # Show goal scorers
        scorers = [p for p in data.player_stats if p.goals > 0]
        if scorers:
            text += "\n⚽ <b>Голы:</b>\n"
            scorer_ids = [s.user_id for s in scorers]
            # Fetch names
            result = await self.session.execute(select(User).where(User.user_id.in_(scorer_ids)))
            users_map = {u.user_id: u.full_name for u in result.scalars().all()}
            
            for s in scorers:
                name = users_map.get(s.user_id, "Неизвестный")
                text += f"- {name}: {s.goals}\n"

        from app.bot.main import bot
        
        if game.message_id:
            await bot.send_message(chat_id=game.chat_id, text=text)
        else:
             logger.info(f"Silent finish for {game.id}")
        
        return game



