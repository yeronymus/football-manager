from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.uow import UnitOfWork

from app.db.models import User, Signup, SignupStatus, GameStatus, Position
from app.core.events import Event

@dataclass
class PlayerJoinedEvent(Event):
    game_id: int
    user_id: int
    signup: Signup
    is_reserve: bool
    message: str

@dataclass
class PlayerLeftEvent(Event):
    game_id: int
    user_id: int
    message: str
    promoted_user: User | None

@dataclass
class JoinResult:
    success: bool
    signup: Signup | None
    message: str
    is_reserve: bool

class RosterService:
    def __init__(self, uow: "UnitOfWork"):
        self.uow = uow

    async def join_player(self, game_id: int, user: User, ignore_limit: bool = False) -> JoinResult:
        # 1. Concurrency Safety: Блокировка строки игры (SELECT ... FOR UPDATE)
        game = await self.uow.game_repo.get_with_lock(game_id)
        
        if not game:
            return JoinResult(False, None, "Игра не найдена", False)
        
        if game.status not in [GameStatus.OPEN, GameStatus.ACTIVE]:
             return JoinResult(False, None, "Запись закрыта!", False)
             
        # 2. Идемпотентность: проверка дублей
        existing = await self.uow.game_repo.get_signup(game_id, user.user_id)
        if existing:
            # Если уже записан, возвращаем успех, но помечаем что ничего не изменилось
            return JoinResult(False, existing, "Вы уже записаны!", existing.status == SignupStatus.RESERVE)

        # 3. Проверка времени
        if game.date_time:
             # Приводим к naive datetime для сравнения, если нужно
             now = datetime.now().replace(tzinfo=None)
             game_dt = game.date_time.replace(tzinfo=None)
             if game_dt < now:
                 return JoinResult(False, None, "Игра уже прошла!", False)

        # 4. Логика слотов (Основной vs Резерв)
        active_count = await self.uow.game_repo.get_active_signups_count(game_id)
        status = SignupStatus.ACTIVE
        alert_msg = "Вы записаны!"
        is_reserve = False
        
        # Логика приоритета вратарей (GK Priority)
        is_gk_priority = False
        if not ignore_limit and game.created_at:
             now_ts = datetime.now().replace(tzinfo=None)
             created_at = game.created_at.replace(tzinfo=None)
             age_hours = (now_ts - created_at).total_seconds() / 3600
             if age_hours < game.gk_hours and user.player_position != Position.GK:
                 slots_left = game.max_players - active_count
                 if slots_left <= 2: # Последние 2 слота держим для вратарей
                     is_gk_priority = True
        
        if (active_count >= game.max_players) or is_gk_priority:
            status = SignupStatus.RESERVE
            alert_msg = "🧤 Места только для вратарей! Вы в РЕЗЕРВЕ." if is_gk_priority else "Резерв (мест нет)"
            is_reserve = True
            
        # 5. Создание записи (Session flush произойдет внутри repo, commit - снаружи)
        signup = self.uow.game_repo.create_signup(game_id, user.user_id, status)
        
        return JoinResult(True, signup, alert_msg, is_reserve)

    async def leave_player(self, game_id: int, user_id: int, is_admin: bool = False) -> tuple[bool, str, User | None]:
        # Блокируем игру, чтобы избежать гонки при выходе и подтягивании резерва
        game = await self.uow.game_repo.get_with_lock(game_id)
        if not game:
            return False, "Игра не найдена.", None
            
        signup = await self.uow.game_repo.get_signup(game_id, user_id)
        if not signup:
            return False, "Вы не записаны.", None

        # Rule: 36 Hours policy
        if game.date_time and not is_admin:
             now = datetime.now().replace(tzinfo=None)
             game_dt = game.date_time.replace(tzinfo=None)
             time_to_game = game_dt - now
             if time_to_game.total_seconds() < 36 * 3600:
                 return False, "Слишком поздно! Пишите админу.", None
        
        was_active = (signup.status == SignupStatus.ACTIVE)
        
        await self.uow.game_repo.delete_signup(signup)
        
        promoted_user = None
        if was_active:
            # Автоматически переводим первого из резерва
            reserve_row = await self.uow.game_repo.get_first_reserve(game_id)
            if reserve_row:
                res_signup, res_user = reserve_row
                res_signup.status = SignupStatus.ACTIVE
                promoted_user = res_user
        
        return True, "Вы выписались.", promoted_user

    async def recalculate_roster(self, game_id: int) -> bool:
        """
        Recalculates the active/reserve status for all signups in a game.
        """
        # 1. Fetch Game and Lock
        game = await self.uow.game_repo.get_with_lock(game_id)
        if not game: return False
        
        # 2. Fetch All Signups Sorted by Time
        signups_with_user = await self.uow.game_repo.get_all_signups_sorted(game_id)
        
        # 3. Logic Setup
        active_count = 0
        gk_reserved_slots = 0
        
        # Check GK Priority Window
        is_gk_window = False
        if game.created_at:
             now_ts = datetime.now().replace(tzinfo=None)
             created_at = game.created_at.replace(tzinfo=None)
             age_hours = (now_ts - created_at).total_seconds() / 3600
             if age_hours < game.gk_hours:
                 is_gk_window = True
                 gk_reserved_slots = 2

        # 4. Iterate and Assign
        for signup, user in signups_with_user:
            is_gk = (user.player_position == Position.GK)
            
            # Effective Max for Non-GKs during Window
            effective_max = game.max_players
            if is_gk_window and not is_gk:
                effective_max = game.max_players - gk_reserved_slots
            
            if active_count < effective_max:
                # Space available
                if signup.status != SignupStatus.ACTIVE:
                    signup.status = SignupStatus.ACTIVE
                active_count += 1
            elif is_gk and active_count < game.max_players:
                # GK Overwrite in Window
                if signup.status != SignupStatus.ACTIVE:
                    signup.status = SignupStatus.ACTIVE
                active_count += 1
            else:
                # No space
                if signup.status != SignupStatus.RESERVE:
                    signup.status = SignupStatus.RESERVE
        
        return True
