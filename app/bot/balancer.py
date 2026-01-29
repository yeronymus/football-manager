from typing import List, Dict
from app.db.models import User, Position, Team
import enum

class Player:
    def __init__(self, user: User):
        self.user = user
        self.position = user.player_position
        self.rating = user.rating or 1200 # Default if None
        self.id = user.user_id
        self.name = user.full_name
        
    def __repr__(self):
        return f"Player({self.name}, {self.position}, {self.rating})"

class BalanceBucket(str, enum.Enum):
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"

def get_bucket_for_position(pos: Position) -> BalanceBucket:
    """Maps a granular position to a balance bucket."""
    # Ensure we handle both Enum object or string value if raw
    val = pos.value if hasattr(pos, 'value') else str(pos)
    
    mapping = {
        "GK": BalanceBucket.GK,
        "LB": BalanceBucket.DEF, "CB": BalanceBucket.DEF, "RB": BalanceBucket.DEF,
        "CDM": BalanceBucket.MID, "CM": BalanceBucket.MID, "CAM": BalanceBucket.MID, 
        "LM": BalanceBucket.MID, "RM": BalanceBucket.MID,
        "LW": BalanceBucket.FWD, "RW": BalanceBucket.FWD, "FWD": BalanceBucket.FWD
    }
    return mapping.get(val, BalanceBucket.MID) # Fallback to MID

def balance_teams(players: List[Player], team_count: int = 2) -> List[List[Player]]:
    """
    Balances players into N teams.
    Algorithm: Water-filling (Greedy) by Count then Rating.
    """
    if not players:
        return [[] for _ in range(team_count)]

    teams: List[List[Player]] = [[] for _ in range(team_count)]
    
    # 1. Bucket by position
    buckets: Dict[BalanceBucket, List[Player]] = {b: [] for b in BalanceBucket}
    
    for p in players:
        bucket = get_bucket_for_position(p.position)
        buckets[bucket].append(p)

    # Sort each bucket by rating descending (Strongest first)
    for b in buckets:
        buckets[b].sort(key=lambda x: x.rating, reverse=True)

    # 2. Distribute GKs (Round Robin)
    # We essentially treat GKs effectively as specific key players.
    gks = buckets[BalanceBucket.GK]
    gk_idx = 0
    while gks:
        # Assign to team with fewest players, then weakest rating? 
        # Or just Strict Round Robin for GKs?
        # Usually GKs are limited (e.g. 2 GKs for 2 teams).
        # Let's use the same "weakest/empty team" logic for GKs too.
        
        teams.sort(key=lambda t: (len(t), sum(x.rating for x in t)))
        teams[0].append(gks.pop(0))

    # 3. Distribute Rest (DEF -> MID -> FWD)
    # Merging remaning GKs into DEF is technically handled by just processing GKs separately.
    # If GKs remain (more GKs than teams?), they are already distributed above.
    
    ordered_groups = [
        buckets[BalanceBucket.DEF], 
        buckets[BalanceBucket.MID], 
        buckets[BalanceBucket.FWD]
    ]
    
    for group in ordered_groups:
        for p in group:
            # Sort teams: 
            # 1. Fewest players (fill gaps)
            # 2. Lowest Total Rating (balance strength)
            teams.sort(key=lambda t: (len(t), sum(x.rating for x in t)))
            teams[0].append(p)

    return teams
