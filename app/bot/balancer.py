from typing import List, Tuple
from app.db.models import User, Position, Team
import random

class Player:
    def __init__(self, user: User):
        self.user = user
        self.position = user.player_position
        self.rating = user.rating or 1200 # Default if None
        self.id = user.user_id
        self.name = user.full_name
        
    def __repr__(self):
        return f"Player({self.name}, {self.position}, {self.rating})"

def balance_teams(players: List[Player], team_count: int = 2) -> List[List[Player]]:
    """
    Balances players into N teams (default 2) based on position and rating (MMR).

    **Algorithm:**
    1.  **Grouping:** Players are grouped by position (GK, DEF, MID, FWD).
    2.  **Sorting:** Each group is sorted by rating (Descending).
    3.  **GK Distribution:** Goalkeepers are distributed first, one per team if possible.
    4.  **Snake Draft / Greedy:** Remaining players (DEF -> MID -> FWD) are distributed.
        - The player is assigned to the team with the *fewest players*.
        - If counts are equal, they are assigned to the team with the *lowest total MMR*.

    Args:
        players: List of Player objects containing user data, position, and rating.
        team_count: Number of teams to create (e.g., 2 or 3).

    Returns:
        A list of lists, where each inner list represents a team.
        Example: [[p1, p2], [p3, p4], [p5, p6]] for 3 teams.
    """
    if not players:
        return [[] for _ in range(team_count)]

    # Initialize teams
    teams = [[] for _ in range(team_count)]
    
    # 1. Bucket by position
    buckets = {
        "GK": [],
        "DEF": [],
        "MID": [],
        "FWD": []
    }
    
    for p in players:
        pos_str = str(p.position.value) if hasattr(p.position, 'value') else str(p.position)
        if pos_str in buckets:
            buckets[pos_str].append(p)
        else:
            buckets["MID"].append(p)

    # Sort buckets by rating desc
    for key in buckets:
        buckets[key].sort(key=lambda x: x.rating, reverse=True)

    # 2. Distribute GKs
    # Simple logic: One GK per team if available, strong GKs spread out
    gks = buckets["GK"]
    
    # Sort teams by strength (initially 0) to give best GK to weakest team? 
    # Or strict snake draft?
    # Let's simple round-robin GKs
    
    # Current index for distribution
    team_indices = list(range(team_count))
    
    while gks and any(len(t) == 0 for t in teams): # Prioritize filling empty teams with GKs first?
         # No, just distribute logic.
         pass

    # Alternative GK Logic:
    # Assign top GKs to different teams
    for i in range(min(len(gks), team_count)):
        teams[i].append(gks.pop(0))
    
    # Remaining GKs become DEF
    buckets["DEF"].extend(gks)
    buckets["DEF"].sort(key=lambda x: x.rating, reverse=True)

    # 3. Distribute Rest (Snake Draft logic based on Team Rating)
    ordered_groups = [buckets["DEF"], buckets["MID"], buckets["FWD"]]
    
    for group in ordered_groups:
        for p in group:
            # Find team with lowest total rating (or lowest count if unbalanced?)
            # Prioritize count balance first, then rating?
            # User wants 18 players -> 3 teams of 6.
            
            # Sort teams by (count, rating)
            # We want to add to the team with MIN count, then MIN rating
            teams.sort(key=lambda t: (len(t), sum(x.rating for x in t)))
            
            # Add to the first one
            teams[0].append(p)

    return teams

