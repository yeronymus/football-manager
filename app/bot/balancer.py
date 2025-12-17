from typing import List, Tuple
from app.db.models import User, Position, Team
import random

class Player:
    def __init__(self, user: User):
        self.user = user
        self.position = user.player_position
        self.rating = user.rating
        self.games_played = user.games_played
        self.id = user.user_id
        
    def __repr__(self):
        return f"Player({self.id}, {self.position}, {self.rating})"

def balance_teams(players: List[Player]) -> Tuple[List[Player], List[Player]]:
    # 1. Bucket by position
    gks = [p for p in players if p.position == Position.GK]
    defs = [p for p in players if p.position == Position.DEF]
    mids = [p for p in players if p.position == Position.MID]
    fwds = [p for p in players if p.position == Position.FWD]
    
    # Sort all groups by rating (strongest first)
    for group in [gks, defs, mids, fwds]:
        group.sort(key=lambda x: x.rating, reverse=True)

    team_a = []
    team_b = []

    def add_to_team(player, t_a, t_b):
        # Helper to add player to the team that needs them more (balance count, then MMR)
        len_a, len_b = len(t_a), len(t_b)
        mmr_a, mmr_b = sum(p.rating for p in t_a), sum(p.rating for p in t_b)

        if len_a < len_b:
            t_a.append(player)
        elif len_b < len_a:
            t_b.append(player)
        else:
            # If counts equal, add to weaker team by MMR
            if mmr_a <= mmr_b:
                t_a.append(player)
            else:
                t_b.append(player)

    # 2. Distribute each position group
    # We distribute group by group to ensure "Mirrored" formation (e.g. 3 DEFs vs 3 DEFs)
    
    # GKs first
    for p in gks:
        add_to_team(p, team_a, team_b)
        
    # DEFs second
    for p in defs:
        add_to_team(p, team_a, team_b)

    # MIDs third
    for p in mids:
        add_to_team(p, team_a, team_b)

    # FWDs last
    for p in fwds:
        add_to_team(p, team_a, team_b)

    return team_a, team_b
