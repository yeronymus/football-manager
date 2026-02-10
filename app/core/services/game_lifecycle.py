from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from datetime import datetime
import logging

from app.db.models import Game, Chat, Signup, SignupStatus, GameStatus, GameStats, User, Team
from app.api.schemas import GameCreate, GameUpdate, GameFinishRequest
from app.core.services.stats import StatsService
from app.infrastructure.scheduler.service import SchedulerService

if TYPE_CHECKING:
    from app.core.uow import UnitOfWork

logger = logging.getLogger(__name__)

class GameLifecycleService:
    def __init__(self, uow: "UnitOfWork", scheduler: SchedulerService, stats: StatsService):
        self.uow = uow
        self.scheduler = scheduler
        self.stats = stats

    @property
    def session(self) -> AsyncSession:
        return self.uow.session

    async def create_game(self, data: GameCreate, creator_id: int) -> Game:
        """
        Creates a new game, handles auto-joins, and schedules lifecycle tasks.
        """
        # 1. Ensure Chat Exists
        chat = await self.session.get(Chat, data.chat_id)
        if not chat:
            # Create a stub if missing.
            chat = Chat(chat_id=data.chat_id, title="Unknown Chat (Auto-created)")
            self.session.add(chat)
            await self.session.flush()

        # 2. Create Game
        game = Game(
            chat_id=data.chat_id,
            created_by=creator_id,
            date_time=data.date_time,
            location=data.location,
            max_players=data.max_players,
            price=data.price,
            payment_info=data.payment_info,
            team_count=data.team_count,
            gk_hours=data.gk_hours,
            duration=data.duration,
            status=GameStatus.OPEN
        )
        self.session.add(game)
        await self.session.flush() # To get ID

        # 3. Auto-Join Admins
        if data.auto_join_ids:
            # We assume users exist or created by caller.
            for admin_id in data.auto_join_ids:
                q = select(Signup).where(Signup.game_id == game.id, Signup.user_id == admin_id)
                res = await self.session.execute(q)
                if not res.scalar_one_or_none():
                    signup = Signup(game_id=game.id, user_id=admin_id, status=SignupStatus.ACTIVE)
                    self.session.add(signup)
        
        # 4. Schedule Tasks
        # Helper to check past (naive/aware mix handled by datetime.now(tz))
        tz = game.date_time.tzinfo
        now_tz = datetime.now(tz) if tz else datetime.now()
        is_past = game.date_time < now_tz
        
        if not is_past:
            if data.publish_at:
                pub_at = data.publish_at
                # Ensure compare aware vs aware
                if pub_at.tzinfo is None and tz:
                    pub_at = pub_at.replace(tzinfo=tz)
                
                if pub_at > now_tz:
                    self.scheduler.schedule_publish(game.id, pub_at)
            
            self.scheduler.schedule_game_lifecycle(game)
        
        # No Commit here. Caller must commit.
        return game

    async def update_game(self, data: GameUpdate) -> tuple[Game, list[str]]:
        """
        Updates game and reschedules tasks. Returns (Game, changes_list).
        """
        game = await self.session.get(Game, data.game_id)
        if not game:
            raise ValueError("Game not found")
            
        changes = []
        
        # Update Fields
        if data.location and data.location != game.location:
             changes.append(f"📍 Локация: {game.location} -> {data.location}")
             game.location = data.location
             
        if data.date_time:
             if game.date_time != data.date_time:
                 old_str = game.date_time.strftime('%d.%m %H:%M')
                 new_str = data.date_time.strftime('%d.%m %H:%M')
                 if old_str != new_str:
                     changes.append(f"📅 Дата: {old_str} -> {new_str}")
                 
                 game.date_time = data.date_time
                 
                 # Reschedule
                 self.scheduler.cancel_game_tasks(game.id)
                 now_tz = datetime.now(game.date_time.tzinfo) if game.date_time.tzinfo else datetime.now()
                 if game.date_time > now_tz:
                     self.scheduler.schedule_voting(game.id, game.date_time)
                     self.scheduler.schedule_admin_reminder(game.id, game.date_time)
        
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
             
        # No Commit.
        return game, changes

    async def finish_game(self, data: GameFinishRequest) -> Game:
        """
        Finishes game, saves stats, applies ELO.
        """
        game = await self.session.get(Game, data.game_id)
        if not game:
            raise ValueError("Game not found")
            
        # Revert if already finished
        if game.status == GameStatus.FINISHED:
             await self.stats.revert_stats(game.id)
             await self.session.execute(
                 delete(GameStats).where(GameStats.game_id == game.id)
             )
        
        # Update Game
        game.score_a = data.score_a
        game.score_b = data.score_b
        game.winner_team = data.winner_team
        game.status = GameStatus.FINISHED
        
        # Process Inputs for Manual Stats
        mvp_ids = set()
        if data.mvp_user_id: mvp_ids.add(data.mvp_user_id)
        if data.mvp_team_a: mvp_ids.add(data.mvp_team_a)
        if data.mvp_team_b: mvp_ids.add(data.mvp_team_b)
        
        processed_users = set()
        
        # Helper to get user obj for counter update
        async def increment_mvp_counter(uid):
            u = await self.session.get(User, uid)
            if u: u.stats_mvp += 1

        if data.player_stats:
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
                    processed_users.add(p_stat.user_id)
                    
                    if is_mvp:
                        await increment_mvp_counter(p_stat.user_id)
        
        # Handle MVPs with no goals
        for mid in mvp_ids:
            if mid not in processed_users:
                self.session.add(GameStats(game_id=game.id, user_id=mid, goals=0, is_mvp=True))
                processed_users.add(mid) # Avoid double add if loop logic changes
                await increment_mvp_counter(mid)
                
        # Call Stats Service for Ratings
        await self.stats.apply_game_results(game, mvp_ids)
        
        # No Commit.
        return game


