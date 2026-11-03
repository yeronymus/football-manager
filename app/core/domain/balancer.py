from abc import ABC, abstractmethod
import enum
import random
from typing import List, Optional
from app.db.models import Position, User


class Player:
    def __init__(self, user: User, rating_override: Optional[int] = None):
        self.user = user
        self.position = user.player_position
        self.alt_positions = []
        if user.alt_positions:
            if isinstance(user.alt_positions, list):
                self.alt_positions = user.alt_positions
            elif isinstance(user.alt_positions, str):
                self.alt_positions = [x.strip() for x in user.alt_positions.split(",")]

        self.rating = (
            rating_override if rating_override is not None else (user.rating or 100)
        )
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
        "LB": BalanceBucket.DEF,
        "CB": BalanceBucket.DEF,
        "RB": BalanceBucket.DEF,
        "LWB": BalanceBucket.DEF,
        "RWB": BalanceBucket.DEF,
        "CDM": BalanceBucket.MID,
        "CM": BalanceBucket.MID,
        "CAM": BalanceBucket.MID,
        "LM": BalanceBucket.MID,
        "RM": BalanceBucket.MID,
        "LW": BalanceBucket.FWD,
        "RW": BalanceBucket.FWD,
        "FWD": BalanceBucket.FWD,
        "ST": BalanceBucket.FWD,
        "CF": BalanceBucket.FWD,
    }
    return mapping.get(pos_str, BalanceBucket.MID)


def get_bucket_for_position(pos: Position) -> BalanceBucket:
    val = pos.value if hasattr(pos, "value") else str(pos)
    return get_bucket_for_position_str(val)


class BalancingStrategy(ABC):
    """Abstract Base Class for team balancing algorithms."""

    @abstractmethod
    def balance(self, players: List[Player], team_count: int) -> List[List[Player]]:
        pass


class RoleBasedBalancingStrategy(BalancingStrategy):
    """
    Role-aware balancing strategy:
    1. Satisfies GK requirements across teams.
    2. Satisfies DEF requirements across teams.
    3. Distributes remaining players by role & strength without mutating team slot indices.
    """

    def balance(self, players: List[Player], team_count: int) -> List[List[Player]]:
        if not players:
            return [[] for _ in range(team_count)]

        teams: List[List[Player]] = [[] for _ in range(team_count)]

        def fits_bucket(p: Player, bucket: BalanceBucket) -> bool:
            if get_bucket_for_position(p.position) == bucket:
                return True
            for alt in p.alt_positions:
                if get_bucket_for_position_str(alt) == bucket:
                    return True
            return False

        pool = players[:]

        # 1. GK Phase
        gks_assigned = 0
        while gks_assigned < team_count:
            candidates = [
                p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.GK
            ]
            if not candidates:
                candidates = [p for p in pool if "GK" in p.alt_positions]
            if not candidates:
                break

            candidates.sort(key=lambda x: x.rating, reverse=True)
            best_gk = candidates[0]
            teams[gks_assigned].append(best_gk)
            pool.remove(best_gk)
            gks_assigned += 1

        # 2. DEF Phase
        def_target_per_team = 3
        for _ in range(def_target_per_team):
            for t_idx in range(team_count):
                candidates = [
                    p
                    for p in pool
                    if get_bucket_for_position(p.position) == BalanceBucket.DEF
                ]
                if not candidates:
                    candidates = [p for p in pool if fits_bucket(p, BalanceBucket.DEF)]
                if candidates:
                    candidates.sort(key=lambda x: x.rating, reverse=True)
                    pick = candidates[0]
                    teams[t_idx].append(pick)
                    pool.remove(pick)

        # 3. Distribute Remaining by Role & Strength (preserving team index order!)
        def distribute_list(subpool: List[Player]):
            subpool.sort(key=lambda x: x.rating, reverse=True)
            for p in subpool:
                target_idx = min(
                    range(team_count),
                    key=lambda idx: (
                        len(teams[idx]),
                        sum(x.rating for x in teams[idx]),
                    ),
                )
                teams[target_idx].append(p)

        rem_mids = [
            p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.MID
        ]
        rem_fwds = [
            p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.FWD
        ]
        rem_defs = [
            p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.DEF
        ]
        rem_gks = [
            p for p in pool if get_bucket_for_position(p.position) == BalanceBucket.GK
        ]

        distribute_list(rem_mids)
        distribute_list(rem_fwds)
        distribute_list(rem_defs)
        distribute_list(rem_gks)

        pool_ids = set(p.id for p in pool)
        dist_ids = set(p.id for p in rem_mids + rem_fwds + rem_defs + rem_gks)
        leftover_ids = pool_ids - dist_ids
        leftovers = [p for p in pool if p.id in leftover_ids]
        distribute_list(leftovers)

        return teams


class RatingSnakeBalancingStrategy(BalancingStrategy):
    """Pure ELO-based serpentine snake draft."""

    def balance(self, players: List[Player], team_count: int) -> List[List[Player]]:
        if not players:
            return [[] for _ in range(team_count)]

        teams: List[List[Player]] = [[] for _ in range(team_count)]
        sorted_players = sorted(players, key=lambda x: x.rating, reverse=True)

        for idx, player in enumerate(sorted_players):
            round_num = idx // team_count
            offset = idx % team_count
            t_idx = offset if round_num % 2 == 0 else (team_count - 1 - offset)
            teams[t_idx].append(player)

        return teams


class RandomBalancingStrategy(BalancingStrategy):
    """Random distribution for friendly matches."""

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

    def balance_teams(
        self, players: List[Player], team_count: int
    ) -> List[List[Player]]:
        return self._strategy.balance(players, team_count)


def balance_teams(players: List[Player], team_count: int = 2) -> List[List[Player]]:
    balancer = TeamBalancer(RoleBasedBalancingStrategy())
    return balancer.balance_teams(players, team_count)
