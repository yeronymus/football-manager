from typing import List, Tuple
from app.db.models import User, Position, Team
import random

class Player:
    def __init__(self, user: User):
        self.user = user
        self.rating = user.rating
        self.position = user.position
        self.id = user.user_id

def balance_teams(players: List[User]) -> Tuple[List[User], List[User]]:
    # 1. Separate Goalkeepers
    # If 0 GKs, list is empty, code won't break.
    gks = [p for p in players if p.position == Position.GK]
    field = [p for p in players if p.position != Position.GK]
    
    # Sort all by rating (strongest first)
    gks.sort(key=lambda x: x.rating, reverse=True)
    field.sort(key=lambda x: x.rating, reverse=True)

    team_a = []
    team_b = []

    # Distribute GKs "snake" style so tops don't end up in same team
    for i, gk in enumerate(gks):
        if i % 2 == 0:
            team_a.append(gk)
        else:
            team_b.append(gk)

    # 2. Adaptive distribution of field players
    # Give next strong player to the "weaker" team
    # (by count first, then by rating)
    
    for player in field:
        len_a = len(team_a)
        len_b = len(team_b)
        
        # Calculate current team strength
        mmr_a = sum(p.rating for p in team_a)
        mmr_b = sum(p.rating for p in team_b)
        
        # HEURISTIC:
        # If one team has fewer people - put player there (balance count)
        if len_a < len_b:
            team_a.append(player)
        elif len_b < len_a:
            team_b.append(player)
        else:
            # If counts equal, put where less MMR
            if mmr_a <= mmr_b:
                team_a.append(player)
            else:
                team_b.append(player)

    return team_a, team_b
