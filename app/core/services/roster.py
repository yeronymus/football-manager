from dataclasses import dataclass
from datetime import datetime, timedelta
from app.core.repositories.game_repo import GameRepository
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
    def __init__(self, game_repo: GameRepository):
        self.game_repo = game_repo

    async def join_player(self, game_id: int, user: User, ignore_limit: bool = False) -> JoinResult:
        # 1. Concurrency Safety: Lock Game Row
        game = await self.game_repo.get_with_lock(game_id)
        if not game:
            return JoinResult(False, None, "Игра не найдена", False)
        
        # 2. Status Check
        if game.status not in [GameStatus.OPEN, GameStatus.ACTIVE]:
             return JoinResult(False, None, "Запись закрыта!", False)
             
        # 3. Duplicate Check
        existing = await self.game_repo.get_signup(game_id, user.user_id)
        if existing:
            return JoinResult(False, existing, "Вы уже записаны!", existing.status == SignupStatus.RESERVE)

         # 4. Time Check
        if game.date_time:
             now_tz = datetime.now(game.date_time.tzinfo) if game.date_time.tzinfo else datetime.now()
             if game.date_time < now_tz:
                 return JoinResult(False, None, "Игра уже прошла!", False)

        # 5. Determine Status (Active vs Reserve)
        active_count = await self.game_repo.get_active_signups_count(game_id)
        
        status = SignupStatus.ACTIVE
        alert_msg = "Вы записаны!"
        is_reserve = False
        
        # GK Priority Logic
        is_gk_priority = False
        
        if not ignore_limit:
            # Check GK Window
            if game.created_at:
                 now_tz = datetime.now(game.created_at.tzinfo) if game.created_at.tzinfo else datetime.now()
                 age_hours = (now_tz - game.created_at).total_seconds() / 3600
                 
                 if age_hours < game.gk_hours:
                     if user.player_position != Position.GK:
                         slots_left = game.max_players - active_count
                         if slots_left <= 2:
                             is_gk_priority = True
            
            if is_gk_priority:
                status = SignupStatus.RESERVE
                alert_msg = "🧤 Места только для вратарей! Вы в РЕЗЕРВЕ."
                is_reserve = True
            elif active_count >= game.max_players:
                status = SignupStatus.RESERVE
                alert_msg = "Резерв (мест нет)"
                is_reserve = True
        else:
            alert_msg = "Вы записаны (Администратор)!"
            
        # 6. Create Signup (NO COMMIT)
        signup = self.game_repo.create_signup(game_id, user.user_id, status)
        
        return JoinResult(True, signup, alert_msg, is_reserve)

    async def leave_player(self, game_id: int, user_id: int, is_admin: bool = False) -> tuple[bool, str, User | None]:
        # 1. Lock Game
        game = await self.game_repo.get_with_lock(game_id)
        if not game:
            return False, "Игра не найдена.", None
            
        # 2. Check Signup
        signup = await self.game_repo.get_signup(game_id, user_id)
        if not signup:
            return False, "Вы не записаны.", None

        # 3. 36h Rule
        if game.date_time and not is_admin:
             now_tz = datetime.now(game.date_time.tzinfo) if game.date_time.tzinfo else datetime.now()
             time_diff = game.date_time - now_tz
             if time_diff.total_seconds() < 36 * 3600:
                 return False, "Слишком поздно выписываться! Пишите админам.", None
        
        was_active = (signup.status == SignupStatus.ACTIVE)
        
        # 4. Delete (NO COMMIT)
        await self.game_repo.delete_signup(signup)
        
        # 5. Auto-Promote
        promoted_user = None
        if was_active:
            reserve_row = await self.game_repo.get_first_reserve(game_id)
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
        game = await self.game_repo.get_with_lock(game_id)
        if not game: return False
        
        # 2. Fetch All Signups Sorted by Time
        signups_with_user = await self.game_repo.get_all_signups_sorted(game_id)
        
        # 3. Logic Setup
        active_count = 0
        gk_reserved_slots = 0
        
        # Check GK Priority Window
        is_gk_window = False
        if game.created_at:
             now_tz = datetime.now(game.created_at.tzinfo) if game.created_at.tzinfo else datetime.now()
             age_hours = (now_tz - game.created_at).total_seconds() / 3600
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
