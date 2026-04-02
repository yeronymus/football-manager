from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.uow import UnitOfWork

from app.db.models import User, Signup, SignupStatus, GameStatus, Position, Team
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

        # 3. Проверка времени (Game Date limits)
        if game.date_time:
             now = datetime.now().replace(tzinfo=None)
             game_dt = game.date_time.replace(tzinfo=None)
             if game_dt < now:
                 return JoinResult(False, None, "Игра уже прошла!", False)

        # 3.1 Configurable Registration Window (Game #6+)
        # If registration_hours is set (> 0), we enforce it.
        if game.created_at and game.registration_hours and game.registration_hours > 0 and not ignore_limit:
             now_ts = datetime.now().replace(tzinfo=None)
             created_at = game.created_at.replace(tzinfo=None)
             diff = (now_ts - created_at).total_seconds() / 3600
             if diff > float(game.registration_hours):
                  return JoinResult(False, None, f"⏳ Запись закрыта (прошло {game.registration_hours} ч.)", False)

        # 3.2 Total Signup Limit
        if getattr(game, 'signup_limit', None) and game.signup_limit > 0 and not ignore_limit:
             total_count = await self.uow.game_repo.get_total_signups_count(game_id)
             if total_count >= game.signup_limit:
                  return JoinResult(False, None, f"❌ Мест нет! (Лимит {game.signup_limit})", False)

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

    async def balance_teams(self, game_id: int) -> list[tuple[User, Team]]:
        """
        Balances teams for a game using domain logic.
        """
        from app.core.domain.balancer import balance_teams, Player as DomainPlayer, BalanceBucket
        
        # 1. Get Active Players
        active_rows = await self.uow.game_repo.get_active_players(game_id)
        if not active_rows:
            return []
            
        players = [DomainPlayer(user) for user, _ in active_rows]
        
        # 2. Run Algorithm
        teams = balance_teams(players, team_count=2) # Assuming 2 teams for now? Or get from Game?
        # Ideally get team_count from Game.
        game = await self.uow.game_repo.get_game(game_id)
        if game and game.team_count:
             teams = balance_teams(players, team_count=game.team_count)

        # 3. Update Signups
        # Map user_id -> Team
        user_team_map = {}
        for i, team_list in enumerate(teams):
            team_enum = Team.A
            if i == 1: team_enum = Team.B
            elif i == 2: team_enum = Team.C
            
            for p in team_list:
                user_team_map[p.id] = team_enum
                
        # Bulk Update or Iterative
        for user, signup in active_rows:
            if user.user_id in user_team_map:
                signup.team = user_team_map[user.user_id]
            else:
                signup.team = None # Should not happen if all active are balanced
                
        return [] # Return structure not strictly defined by caller yet, but endpoint returns status

    async def update_teams(self, game_id: int, team_a: list[int], team_b: list[int], team_c: list[int], unassigned: list[int], positions: dict) -> list[int]:
        """
        Updates team assignments and handles manual promotions.
        """
        # 1. Get All Signups
        signups = await self.uow.game_repo.get_all_active_and_reserve(game_id)
        signup_map = {s.user_id: s for s in signups}
        
        promoted_ids = []
        
        # Helper for assigning teams (always ensures they are ACTIVE)
        def update_signup(uid, team_enum):
            if uid in signup_map:
                s = signup_map[uid]
                # Promote to Active if they were Reserve but are now in a team
                if s.status == SignupStatus.RESERVE:
                    s.status = SignupStatus.ACTIVE
                    promoted_ids.append(uid)
                s.team = team_enum
                
                # Update Position if provided
                if str(uid) in positions:
                    try:
                        s.position = Position(positions[str(uid)])
                    except: pass
                elif uid in positions:
                     try:
                        s.position = Position(positions[uid])
                     except: pass

        # 2. Update Teams (Manual override)
        for uid in team_a: update_signup(uid, Team.A)
        for uid in team_b: update_signup(uid, Team.B)
        for uid in team_c or []: update_signup(uid, Team.C)
        
        # 3. Handle Unassigned Pool (Auto-filling Active statuses)
        # Count how many we already have in teams
        active_count = len(team_a) + len(team_b) + (len(team_c) if team_c else 0)
        
        # Sort unassigned pool by registration time to be fair (FIFO)
        unassigned_signups = [signup_map[uid] for uid in unassigned if uid in signup_map]
        unassigned_signups.sort(key=lambda s: s.created_at)
        
        for s in unassigned_signups:
            s.team = None
            if active_count < game.max_players:
                # If there's space, ensure they are ACTIVE
                if s.status == SignupStatus.RESERVE:
                    s.status = SignupStatus.ACTIVE
                    promoted_ids.append(s.user_id)
                active_count += 1
            else:
                # If no space, ensure they are RESERVE
                s.status = SignupStatus.RESERVE
        
        # Finally: Demote anyone who wasn't in list A, B, C or Unassigned
        picked_ids = set(team_a) | set(team_b) | set(team_c or []) | set(unassigned)
        for uid, s in signup_map.items():
            if uid not in picked_ids:
                s.status = SignupStatus.RESERVE
                s.team = None

        return promoted_ids
