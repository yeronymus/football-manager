from typing import List, Dict
from app.db.models import User, Position, Team
import enum
import random
from abc import ABC, abstractmethod

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


# ===========================================================================
# DESIGN PATTERN: STRATEGY PATTERN FOR TEAM BALANCING
# ===========================================================================

class BalancingStrategy(ABC):
    """Abstract Base Class for team balancing algorithms."""
    @abstractmethod
    def balance(self, players: List[Player], team_count: int) -> List[List[Player]]:
        pass


class RoleBasedBalancingStrategy(BalancingStrategy):
    """
    Advanced balancing that:
    1. Satisfies GK requirements.
    2. Satisfies DEF requirements (target: 3 per team).
    3. Decouples remaining by role & strength.
    """
    def balance(self, players: List[Player], team_count: int) -> List[List[Player]]:
        if not players:
            return [[] for _ in range(team_count)]

        teams: List[List[Player]] = [[] for _ in range(team_count)]
        
        def fits_bucket(p: Player, bucket: BalanceBucket) -> bool:
            if get_bucket_for_position(p.position) == bucket: return True
            for alt in p.alt_positions:
                if get_bucket_for_position_str(alt) == bucket: return True
            return False

        pool = players[:]
        
        # 1. GK Phase
        gks_assigned = 0
        while gks_assigned < team_count:
            candidates = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.GK]
            if not candidates:
                candidates = [p for p in pool if "GK" in p.alt_positions]
            if not candidates:
                break
                
            candidates.sort(key=lambda x: x.rating, reverse=True)
            best_gk = candidates[0]
            teams[gks_assigned].append(best_gk)
            pool.remove(best_gk)
            gks_assigned += 1
            
        # 2. DEF Phase (target 3 defenders per team)
        def_target_per_team = 3 
        for _ in range(def_target_per_team):
            for t_idx in range(team_count):
                candidates = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.DEF]
                if not candidates:
                    candidates = [p for p in pool if fits_bucket(p, BalanceBucket.DEF)]
                if candidates:
                    candidates.sort(key=lambda x: x.rating, reverse=True)
                    pick = candidates[0]
                    teams[t_idx].append(pick)
                    pool.remove(pick)
        
        # 3. Distribute Remaining by Role & Strength
        def distribute_list(subpool: List[Player]):
            subpool.sort(key=lambda x: x.rating, reverse=True)
            for p in subpool:
                # Assign to team with fewest players, break ties with lowest cumulative rating
                teams.sort(key=lambda t: (len(t), sum(x.rating for x in t)))
                teams[0].append(p)

        rem_mids = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.MID]
        rem_fwds = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.FWD]
        rem_defs = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.DEF]
        rem_gks  = [p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.GK]

        distribute_list(rem_mids)
        distribute_list(rem_fwds)
        distribute_list(rem_defs)
        distribute_list(rem_gks)
        
        # Leftovers safety
        pool_ids = set(p.id for p in pool)
        dist_ids = set(p.id for p in rem_mids + rem_fwds + rem_defs + rem_gks)
        leftover_ids = pool_ids - dist_ids
        leftovers = [p for p in pool if p.id in leftover_ids]
        distribute_list(leftovers)

        return teams


class RatingSnakeBalancingStrategy(BalancingStrategy):
    """
    Pure ELO-based snake draft:
    Sorts all players by rating desc and distributes them in a snake pattern (1-2-2-1)
    to achieve near-perfect average ratings.
    """
    def balance(self, players: List[Player], team_count: int) -> List[List[Player]]:
        if not players:
            return [[] for _ in range(team_count)]
            
        teams: List[List[Player]] = [[] for _ in range(team_count)]
        sorted_players = sorted(players, key=lambda x: x.rating, reverse=True)
        
        for idx, player in enumerate(sorted_players):
            round_num = idx // team_count
            offset = idx % team_count
            if round_num % 2 == 0:
                # Left-to-right
                t_idx = offset
            else:
                # Right-to-left
                t_idx = team_count - 1 - offset
            teams[t_idx].append(player)
            
        return teams


class RandomBalancingStrategy(BalancingStrategy):
    """Random distribution for maximum variety in friendly matches."""
    def balance(self, players: List[Player], team_count: int) -> List[List[Player]]:
        if not players:
            return [[] for _ in range(team_count)]
            
        teams: List[List[Player]] = [[] for _ in range(team_count)]
        pool = players[:]
        random.shuffle(pool)
        
        for idx, player in enumerate(pool):
            teams[idx % team_count].append(player)
            
        return teams


class TeamBalancer:
    """Context class that holds and delegates to a BalancingStrategy."""
    def __init__(self, strategy: BalancingStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: BalancingStrategy):
        self._strategy = strategy

    def balance_teams(self, players: List[Player], team_count: int) -> List[List[Player]]:
        return self._strategy.balance(players, team_count)


# Maintain backward compatibility
def balance_teams(players: List[Player], team_count: int = 2) -> List[List[Player]]:
    balancer = TeamBalancer(RoleBasedBalancingStrategy())
    return balancer.balance_teams(players, team_count)
