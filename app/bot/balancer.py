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

def balance_teams(players: List[Player], has_gk_a: bool = True, has_gk_b: bool = True) -> Tuple[List[Player], List[Player]]:
    """
    Balances teams trying to respect positions and MMR.
    Groups players by position, sorts by rating, then distributes.
    
    Args:
        players: List of Player objects.
        has_gk_a: If True, Team A needs a Goalkeeper.
        has_gk_b: If True, Team B needs a Goalkeeper.
    """
    if not players:
        return [], []

    # 1. Bucket by position (Robustly)
    buckets = {
        "GK": [],
        "DEF": [],
        "MID": [],
        "FWD": []
    }
    
    for p in players:
        # Convert to string just in case
        pos_str = str(p.position.value) if hasattr(p.position, 'value') else str(p.position)
        
        if pos_str in buckets:
            buckets[pos_str].append(p)
        else:
            buckets["MID"].append(p) # Default fallback

    # Sort all groups by rating desc
    for key in buckets:
        buckets[key].sort(key=lambda x: x.rating, reverse=True)

    team_a = []
    team_b = []

    def get_mmr(team):
         return sum(p.rating for p in team)

    # 2. Distribute GKs explicitly first
    gks = buckets["GK"]
    
    # If both need GK, distribute top 2
    if has_gk_a and has_gk_b:
        # Distribute strictly
        pass 
    elif has_gk_a and not has_gk_b:
        # Give best GK to A, others to pool
        if gks:
            team_a.append(gks.pop(0))
    elif not has_gk_a and has_gk_b:
        # Give best GK to B, others to pool
        if gks:
            team_b.append(gks.pop(0))
    
    # For remaining GKs or if both needed, treat them as players to distribute
    # Or strict distribution loop?
    # Let's use a simpler approach: 
    # If a team NEEDS a GK, and we have GKs, forced assign.
    
    # Refined GK Logic:
    # If A needs GK, tries to grab one. If B needs GK, tries to grab.
    # Logic:
    # 1. Take required GKs
    # 2. Add remaining GKs to DEF/MID bucket to be distributed normally? Or keep in GK bucket but just distribute?
    
    # Let's keep the standard loop but prioritize slots.
    # Issue: The standard loop tries to equalize COUNT. If A already has 1 (GK) and B has 0, B gets next.
    
    # Re-assemble pool relative to distribution order
    # If we want A to have a GK, we should pre-seed?
    
    # Reset and do pre-seeding approach
    team_a = []
    team_b = []
    
    # Handle GKs separately
    available_gks = list(buckets["GK"])
    
    if has_gk_a and available_gks:
        team_a.append(available_gks.pop(0))
    
    if has_gk_b and available_gks:
        team_b.append(available_gks.pop(0))
        
    # Remaining GKs become defenders (or just players)
    # We add them to DEF bucket for distribution
    buckets["DEF"].extend(available_gks)
    # Sort DEF again to integrate the GKs correctly by rating
    buckets["DEF"].sort(key=lambda x: x.rating, reverse=True)
    
    # 3. Distribute Rest
    # Order: DEF, MID, FWD
    ordered_groups = [buckets["DEF"], buckets["MID"], buckets["FWD"]]
    
    for group in ordered_groups:
        for p in group:
            len_a = len(team_a)
            len_b = len(team_b)
            
            if len_a < len_b:
                team_a.append(p)
            elif len_b < len_a:
                team_b.append(p)
            else:
                # Counts equal, check MMR
                mmr_a = get_mmr(team_a)
                mmr_b = get_mmr(team_b)
                
                # If MMR A < MMR B, A gets player (to boost A)
                # But we should also check if adding P to A makes balance worse?
                # Simple greedy: Give to weaker team
                if mmr_a <= mmr_b:
                    team_a.append(p)
                else:
                    team_b.append(p)

    return team_a, team_b
