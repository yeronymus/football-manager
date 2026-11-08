from abc import ABC, abstractmethod
import enum
import random
from typing import Any, List, Optional


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
    return mapping.get(str(pos_str or "").upper(), BalanceBucket.MID)


def get_bucket_for_position(pos: Any) -> BalanceBucket:
    val = pos.value if hasattr(pos, "value") else str(pos)
    return get_bucket_for_position_str(val)


class Player:
    """
    Domain Player representation for team matchmaking.
    Can be constructed either from an ORM `User` object or directly via pure domain keyword arguments.
    """

    def __init__(
        self,
        user: Any = None,
        rating_override: Optional[int] = None,
        *,
        user_id: Optional[int] = None,
        full_name: Optional[str] = None,
        position: Any = "CM",
        alt_positions: Optional[List[str]] = None,
    ):
        self.user = user
        if user is not None:
            self.position = getattr(user, "player_position", position)
            raw_alts = getattr(user, "alt_positions", None)
            self.alt_positions: List[str] = []
            if raw_alts:
                if isinstance(raw_alts, list):
                    self.alt_positions = list(raw_alts)
                elif isinstance(raw_alts, str):
                    self.alt_positions = [x.strip() for x in raw_alts.split(",") if x.strip()]
            self.rating = (
                rating_override
                if rating_override is not None
                else (getattr(user, "rating", None) or 100)
            )
            self.id = getattr(user, "user_id", user_id or 0)
            self.name = getattr(user, "full_name", full_name or f"Player {self.id}")
        else:
            self.position = position
            self.alt_positions = list(alt_positions or [])
            self.rating = rating_override if rating_override is not None else 100
            self.id = user_id or 0
            self.name = full_name or f"Player {self.id}"

    def __repr__(self) -> str:
        return f"Player({self.name}, {self.position}, {self.rating})"


def _team_spread_sq(teams: List[List[Player]]) -> float:
    """Computes sum of squared deviations of team rating sums from the mean."""
    if not teams:
        return 0.0
    sums = [sum(p.rating for p in t) for t in teams]
    mean = sum(sums) / len(sums)
    return sum((s - mean) ** 2 for s in sums)


def _optimize_same_bucket_2opt(
    teams: List[List[Player]], locked_player_ids: set[int] | None = None
) -> None:
    """
    Deterministic 2-opt local-search optimizer across N teams (ADR-06).
    Swaps players belonging to the same positional BalanceBucket between teams i and j
    whenever the swap strictly reduces the inter-team rating sum variance, keeping team
    sizes and positional bucket counts 100% invariant.
    """
    team_count = len(teams)
    if team_count < 2:
        return
    locked = locked_player_ids or set()

    improved = True
    max_iterations = 64
    iteration = 0
    while improved and iteration < max_iterations:
        improved = False
        iteration += 1
        current_spread = _team_spread_sq(teams)

        for t_a in range(team_count):
            for t_b in range(t_a + 1, team_count):
                for idx_a, p_a in enumerate(teams[t_a]):
                    if p_a.id in locked:
                        continue
                    bucket_a = get_bucket_for_position(p_a.position)
                    for idx_b, p_b in enumerate(teams[t_b]):
                        if p_b.id in locked:
                            continue
                        if get_bucket_for_position(p_b.position) != bucket_a:
                            continue
                        if p_a.rating == p_b.rating:
                            continue

                        # Trial swap
                        teams[t_a][idx_a], teams[t_b][idx_b] = p_b, p_a
                        new_spread = _team_spread_sq(teams)
                        if new_spread + 1e-6 < current_spread:
                            current_spread = new_spread
                            improved = True
                            break
                        else:
                            # Revert swap
                            teams[t_a][idx_a], teams[t_b][idx_b] = p_a, p_b
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break


class BalancingStrategy(ABC):
    """Abstract Base Class for team balancing algorithms."""

    @abstractmethod
    def balance(self, players: List[Player], team_count: int) -> List[List[Player]]:
        pass


class RoleBasedBalancingStrategy(BalancingStrategy):
    """
    Role-aware balancing strategy with weakest-first serpentine drafting and 2-opt local search:
    1. Satisfies GK requirements across teams (locking primary GKs to their assigned team slots).
    2. Satisfies DEF requirements across teams in weakest-first order.
    3. Distributes remaining players by role & strength.
    4. Runs within-bucket 2-opt pairwise optimization to minimize inter-team rating variance.
    """

    def balance(self, players: List[Player], team_count: int) -> List[List[Player]]:
        if not players:
            return [[] for _ in range(team_count)]

        teams: List[List[Player]] = [[] for _ in range(team_count)]
        locked_gk_ids: set[int] = set()

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
            locked_gk_ids.add(best_gk.id)
            pool.remove(best_gk)
            gks_assigned += 1

        # 2. DEF Phase (weakest-team-first serpentine order per defender round)
        def_target_per_team = 3
        for _ in range(def_target_per_team):
            team_order = sorted(
                range(team_count),
                key=lambda idx: (
                    len(teams[idx]),
                    sum(x.rating for x in teams[idx]),
                ),
            )
            for t_idx in team_order:
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

        # 3. Distribute Remaining by Role & Strength
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

        # 4. Within-bucket 2-opt variance minimization (keeping primary GKs locked to their team slots)
        _optimize_same_bucket_2opt(teams, locked_player_ids=locked_gk_ids)

        return teams


class RatingSnakeBalancingStrategy(BalancingStrategy):
    """Pure ELO-based serpentine snake draft with 2-opt refinement."""

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
