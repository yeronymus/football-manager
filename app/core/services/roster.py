from dataclasses import dataclass
from datetime import datetime, timedelta
from app.core.services.base import BaseService
from app.core.repositories.game_repo import GameRepository
from app.db.models import Game, User, Signup, SignupStatus, GameStatus, Position
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

class RosterService(BaseService):
    def __init__(self, game_repo: GameRepository):
        super().__init__()
        self.game_repo = game_repo

    async def join_player(self, game_id: int, user: User, ignore_limit: bool = False) -> JoinResult:
        # 1. Lock Game row
        game = await self.game_repo.get_with_lock(game_id)
        if not game:
            return JoinResult(False, None, "Game not found", False)
        
        # 2. Logic Checks
        if game.status not in [GameStatus.OPEN, GameStatus.ACTIVE]:
             return JoinResult(False, None, "Запись закрыта!", False)
             
        # Check if already signed up (Repository read)
        existing = await self.game_repo.get_signup(game_id, user.user_id)
        if existing:
            return JoinResult(False, existing, "Вы уже записаны!", existing.status == SignupStatus.RESERVE)

         # Check for Past Game
        if game.date_time:
             # Handle TZ awareness if needed, assuming aware for now
             now_tz = datetime.now(game.date_time.tzinfo) if game.date_time.tzinfo else datetime.now()
             if game.date_time < now_tz:
                 return JoinResult(False, None, "Игра уже прошла!", False)

        # 3. Determine Status (Reserve Logic)
        active_count = await self.game_repo.get_active_signups_count(game_id)
        
        status = SignupStatus.ACTIVE
        alert_msg = "Вы записаны!"
        is_reserve = False
        
        # GK Check Logic
        is_gk_priority = False
        
        if not ignore_limit:
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
                alert_msg = "🧤 <b>Последние места для вратарей!</b>\nВы записаны в <b>РЕЗЕРВ</b>. Если вратари не найдутся, администратор перенесет вас в состав."
                is_reserve = True
            elif active_count >= game.max_players:
                status = SignupStatus.RESERVE
                alert_msg = "Резерв (мест нет)"
                is_reserve = True
        else:
            # Force Active (Admin Override)
            status = SignupStatus.ACTIVE
            alert_msg = "Вы записаны (Администратор)!"
            is_reserve = False
            
        # 4. Action
        signup = self.game_repo.create_signup(game_id, user.user_id, status)
        
        # Note: We do NOT commit here. The Controller (Handler) will commit.
        # Event publishing moved to Controller/Handler

        
        return JoinResult(True, signup, alert_msg, is_reserve)

    async def leave_player(self, game_id: int, user_id: int, is_admin: bool = False) -> tuple[bool, str, User | None]:
        """
        Removes a player from the game.
        Returns (Success, Message, PromotedUser).
        PromotedUser is the user who was moved from Reserve to Active (if any).
        """
        # 1. Lock Game
        game = await self.game_repo.get_with_lock(game_id)
        if not game:
            return False, "Игра не найдена.", None
            
        # 2. Check Signup
        signup = await self.game_repo.get_signup(game_id, user_id)
        if not signup:
            return False, "Вы не записаны.", None

        # 3. Time Check (36h rule)
        # TODO: Move 36h to Config/DB
        if game.date_time and not is_admin:
             now_tz = datetime.now(game.date_time.tzinfo) if game.date_time.tzinfo else datetime.now()
             time_diff = game.date_time - now_tz
             if time_diff.total_seconds() < 36 * 3600:
                 return False, "Слишком поздно выписываться! Пишите админам.", None
        
        # 4. Action
        was_active = (signup.status == SignupStatus.ACTIVE)
        await self.game_repo.delete_signup(signup)
        
        # 5. Auto-Promotion Logic
        promoted_user = None
        if was_active:
             # Fetch First Reserve
            reserve_row = await self.game_repo.get_first_reserve(game_id)
            if reserve_row:
                res_signup, res_user = reserve_row
                # Promote
                res_signup.status = SignupStatus.ACTIVE
                promoted_user = res_user
        
        # Event is published by Controller/Handler after commit
        return True, "Вы выписались.", promoted_user




    async def balance_teams(self, game_id: int) -> bool:
        """
        Balances teams using the balancer algorithm and updates Signup records.
        Returns True if successful.
        """
        from app.core.domain.balancer import balance_teams as run_balance_teams, Player
        from app.db.models import Team

        # 1. Lock Game (Implicitly via repo or just fetch?)
        # Balancing is admin action, usually exclusive.
        game = await self.game_repo.get_game(game_id)
        if not game:
             raise ValueError("Game not found")
             
        # 2. Fetch Active Players
        # We need User objects for the balancer
        rows = await self.game_repo.get_active_players(game_id)
        if len(rows) < 1:
            raise ValueError("Not enough players to balance")
            
        players = [r[0] for r in rows] # Extract Users
        
        # 3. Run Algorithm
        wrapped_players = [Player(p) for p in players]
        teams = run_balance_teams(wrapped_players, team_count=game.team_count)
        
        # 4. Map and Save
        team_map = {0: Team.A, 1: Team.B, 2: Team.C}
        
        # Create a map for fast Signup lookup {user_id: signup}
        signup_map = {r[0].user_id: r[1] for r in rows}
        
        for i, team_players in enumerate(teams):
            team_enum = team_map.get(i)
            if not team_enum: continue
            
            for p in team_players:
                if p.id in signup_map:
                    signup_map[p.id].team = team_enum
                    
        # Committing is handled by Controller generally, but here we modify multiple rows.
        # Since we are in Service, we rely on Repo's session.
        # Check if we should commit. BaseService doesn't enforce.
        # Usually Controller calls commit.
        # But for bulk updates, maybe flush?
        # Let's leave commit to Controller.
        return True

    async def update_teams(self, game_id: int, 
                          team_a: list[int], 
                          team_b: list[int], 
                          team_c: list[int] | None, 
                          positions: dict[str, str]) -> list[int]:
        """
        Updates team assignments and positions manually.
        Returns a list of User IDs that were promoted from Reserve to Active.
        """
        from app.db.models import Team, Position
        
        # 1. Fetch all relevant signups (Active + Reserve)
        signups = await self.game_repo.get_all_active_and_reserve(game_id)
        signup_map = {s.user_id: s for s in signups}
        
        promoted_ids = []
        
        # Helper
        def assign_team(uid, team_enum):
            if uid in signup_map:
                s = signup_map[uid]
                s.team = team_enum
                if s.status == SignupStatus.RESERVE:
                    s.status = SignupStatus.ACTIVE
                    promoted_ids.append(uid)

        # 2. Assign Teams
        for uid in team_a: assign_team(uid, Team.A)
        for uid in team_b: assign_team(uid, Team.B)
        if team_c:
            for uid in team_c: assign_team(uid, Team.C)
            
        # 3. Reset others
        assigned_ids = set(team_a) | set(team_b)
        if team_c: assigned_ids |= set(team_c)
        
        for uid, s in signup_map.items():
            if uid not in assigned_ids:
                s.team = None
                
        # 4. Update Positions
        slot_map = {
            "GK": Position.GK,
            "DEF": Position.CB,
            "MID": Position.CM,
            "FWD": Position.FWD
        }
        
        for uid_str, pos_str in positions.items():
            try:
                uid = int(uid_str) # keys are strings in JSON
                if uid in signup_map:
                    # Generic map or Direct Enum
                    new_pos = slot_map.get(pos_str)
                    if not new_pos:
                         # Try fallback
                         try:
                             new_pos = Position(pos_str)
                         except ValueError:
                             continue
                    
                    signup_map[uid].position = new_pos
            except ValueError:
                continue
                
        return promoted_ids
    
    async def recalculate_roster(self, game_id: int) -> bool:
        """
        Recalculates the active/reserve status for all signups in a game based on:
        1. Game Constraints (Max Players)
        2. GK Priority Logic (if applicable)
        3. Join Time (FIFO)
        
        Use this to fix data inconsistencies.
        """
        # 1. Fetch Game and Lock
        game = await self.game_repo.get_with_lock(game_id)
        if not game: return False
        
        # 2. Fetch All Signups Sorted by Time
        # We need a new Repo method or allow access to session?
        # Let's add get_all_signups_sorted to Repo.
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
                 gk_reserved_slots = 2 # Hardcoded or Config? 2 is standard.

        # 4. Iterate and Assign
        for signup, user in signups_with_user:
            # Determine if this user SHOULD be active
            
            # Constraints:
            # 1. Is there space?
            # 2. If GK window, are we encroaching on GK slots?
            
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
                # Special Case: We are in GK Window (implied by effective_max check failing but real max passing?)
                # OR we just have space in general but effective_max was hit?
                # Actually, if is_gk_window is True, effective_max < max_players.
                # If we are here, it means active_count >= effective_max.
                # If active_count < game.max_players, then we are in the "Reserved Zone".
                # If user is GK, they take the slot.
                if signup.status != SignupStatus.ACTIVE:
                    signup.status = SignupStatus.ACTIVE
                active_count += 1
            else:
                # No space
                if signup.status != SignupStatus.RESERVE:
                    signup.status = SignupStatus.RESERVE

        # 5. Commit happens in Controller usually, but this is a maintenance task.
        # We assume caller commits or we do it here if it's a "fix" method?
        # Service methods usually don't commit.
        return True
