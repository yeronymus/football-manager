from typing import List, Dict
from app.db.models import User, Position, Team
import enum

class Player:
    def __init__(self, user: User):
        self.user = user
        self.position = user.player_position
        # Handle alt_positions which might be None, list, or string
        self.alt_positions = []
        if user.alt_positions:
            if isinstance(user.alt_positions, list):
                self.alt_positions = user.alt_positions
            elif isinstance(user.alt_positions, str):
                self.alt_positions = [x.strip() for x in user.alt_positions.split(",")]
                
        self.rating = user.rating or 100 # Default if None
        self.id = user.user_id
        self.name = user.full_name
        
    def __repr__(self):
        return f"Player({self.name}, {self.position}, {self.rating})"

class BalanceBucket(str, enum.Enum):
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"

def get_bucket_for_position_str(pos_str: str) -> BalanceBucket:
    """Maps a position string to a balance bucket."""
    mapping = {
        "GK": BalanceBucket.GK,
        "LB": BalanceBucket.DEF, "CB": BalanceBucket.DEF, "RB": BalanceBucket.DEF, "LWB": BalanceBucket.DEF, "RWB": BalanceBucket.DEF,
        "CDM": BalanceBucket.MID, "CM": BalanceBucket.MID, "CAM": BalanceBucket.MID, 
        "LM": BalanceBucket.MID, "RM": BalanceBucket.MID,
        "LW": BalanceBucket.FWD, "RW": BalanceBucket.FWD, "FWD": BalanceBucket.FWD, "ST": BalanceBucket.FWD, "CF": BalanceBucket.FWD
    }
    return mapping.get(pos_str, BalanceBucket.MID)

def get_bucket_for_position(pos: Position) -> BalanceBucket:
    val = pos.value if hasattr(pos, 'value') else str(pos)
    return get_bucket_for_position_str(val)

def balance_teams(players: List[Player], team_count: int = 2) -> List[List[Player]]:
    """
    Balances players into N teams.
    Enhanced Algorithm:
    1. Satisfy GK requirements (using Primary then Alt).
    2. Satisfy DEF requirements (Target: 3 per team) using Primary then Alt.
    3. Distribute remaining by Strength.
    """
    if not players:
        return [[] for _ in range(team_count)]

    teams: List[List[Player]] = [[] for _ in range(team_count)]
    
    # --- 0. Helper to check if player fits bucket ---
    def fits_bucket(p: Player, bucket: BalanceBucket) -> bool:
        # Check primary
        if get_bucket_for_position(p.position) == bucket: return True
        # Check alts
        for alt in p.alt_positions:
            if get_bucket_for_position_str(alt) == bucket: return True
        return False

    # --- 1. Identify Pool ---
    # We work with a list of available players to assign
    pool = players[:]
    
    # --- 2. GK Phase ---
    # Goal: 1 GK per team.
    # Logic: Find primary GKs first. If not enough, find Alt GKs.
    
    gks_assigned = 0
    while gks_assigned < team_count:
        # Find best candidate for GK
        # Priority 1: Primary GK
        candidates = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.GK]
        
        if not candidates:
            # Priority 2: Alt GK
            candidates = [p for p in pool if "GK" in p.alt_positions]
            
        if not candidates:
            break # No more GKs found
            
        # Sort candidates by rating (descending? or ascending to save strong players for field?)
        # Usually we want best GKs in goal.
        candidates.sort(key=lambda x: x.rating, reverse=True)
        best_gk = candidates[0]
        
        # Assign to team with NO GK yet
        # Find team index = gks_assigned (simple round robin for this phase)
        target_team_idx = gks_assigned
        teams[target_team_idx].append(best_gk)
        
        pool.remove(best_gk)
        gks_assigned += 1
        
    # --- 3. DEF Phase ---
    # Goal: At least 3 Defenders per team? Or just maximize?
    # User said: "Need at least 3 defenders".
    # Let's try to fill 3 slots per team.
    
    def_target_per_team = 3 
    
    # Loop 3 times (for 1st defender, 2nd defender, 3rd defender)
    for _ in range(def_target_per_team):
        # Round robin across teams
        for t_idx in range(team_count):
            # Find best DEF candidate
            # Priority 1: Primary DEF
            candidates = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.DEF]
            
            if not candidates:
                # Priority 2: Alt DEF (Only if we really need them?)
                # If we convert a good MID/FWD to DEF, we might lose attack power.
                # But balanced structure is improved.
                candidates = [p for p in pool if fits_bucket(p, BalanceBucket.DEF)]
                
            if candidates:
                # Pick strongest DEF? Or Weakest?
                # Strongest makes defense solid.
                candidates.sort(key=lambda x: x.rating, reverse=True)
                pick = candidates[0]
                
                teams[t_idx].append(pick)
                pool.remove(pick)
    
    # --- 4. Distribute Remaining by Role ---
    # To avoid one team getting all MIDs and the other all FWDs, we distribute by role.
    
    # helper to distribute a list of players to teams balanced by count and rating
    def distribute_list(subpool: List[Player]):
        subpool.sort(key=lambda x: x.rating, reverse=True)
        for p in subpool:
             # Assign to team with fewest players, break ties with lowest rating
            teams.sort(key=lambda t: (len(t), sum(x.rating for x in t)))
            teams[0].append(p)

    # Buckets for remaining players
    rem_mids = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.MID]
    rem_fwds = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.FWD]
    rem_defs = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.DEF] # Extras
    rem_gks  = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.GK]  # Extras

    # Distribute in order: MID -> FWD -> DEF -> GK (Extras)
    distribute_list(rem_mids)
    distribute_list(rem_fwds)
    distribute_list(rem_defs)
    distribute_list(rem_gks)
    
    # Any leftovers (safety)
    pool_ids = set(p.id for p in pool)
    dist_ids = set(p.id for p in rem_mids + rem_fwds + rem_defs + rem_gks)
    leftover_ids = pool_ids - dist_ids
    leftovers = [p for p in pool if p.id in leftover_ids]
    distribute_list(leftovers)

    return teams
