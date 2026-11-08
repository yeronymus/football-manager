from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Mapping, Sequence

from app.core.domain.tenant_policy import RatingSystem, TenantPolicy


@dataclass(frozen=True)
class ParticipantRatingInput:
    """Pure domain value object representing a participant's state prior to rating calculation."""

    user_id: int
    team: str
    current_rating: int = 100
    games_played: int = 0
    is_mvp: bool = False


class IRatingStrategy(ABC):
    """Pluggable rating strategy interface for 2..N team matches (ADR-06)."""

    @abstractmethod
    def compute_team_base_points(
        self, team_scores: Mapping[str, int], policy: TenantPolicy
    ) -> Dict[str, int]:
        """Computes team-level base delta when applicable."""

    @abstractmethod
    def compute_player_deltas(
        self,
        participants: Sequence[ParticipantRatingInput],
        team_scores: Mapping[str, int],
        policy: TenantPolicy,
    ) -> Dict[int, int]:
        """Computes integer rating delta per user_id."""


class SimplePointsRatingStrategy(IRatingStrategy):
    """
    Configurable rank-interpolated points strategy (`+win / +draw / -loss / +mvp`).
    Supports 2..N teams with tie-aware rank interpolation.
    """

    def compute_team_base_points(
        self, team_scores: Mapping[str, int], policy: TenantPolicy
    ) -> Dict[str, int]:
        if not team_scores:
            return {}

        win_pts = policy.rating_win_points
        draw_pts = policy.rating_draw_points
        loss_pts = policy.rating_loss_points

        unique_scores = sorted(set(team_scores.values()), reverse=True)
        team_points: Dict[str, int] = {}

        for team_key, score in team_scores.items():
            if len(unique_scores) == 1:
                team_points[team_key] = draw_pts
            else:
                rank = unique_scores.index(score)
                max_rank = len(unique_scores) - 1
                pts = win_pts - ((win_pts - loss_pts) * rank / max_rank)
                team_points[team_key] = round(pts)
        return team_points

    def compute_player_deltas(
        self,
        participants: Sequence[ParticipantRatingInput],
        team_scores: Mapping[str, int],
        policy: TenantPolicy,
    ) -> Dict[int, int]:
        team_points = self.compute_team_base_points(team_scores, policy)
        deltas: Dict[int, int] = {}
        for p in participants:
            delta = team_points.get(p.team, policy.rating_loss_points)
            if p.is_mvp:
                delta += policy.rating_mvp_bonus
            deltas[p.user_id] = int(delta)
        return deltas


class DynamicEloRatingStrategy(IRatingStrategy):
    """
    Multi-team pairwise Dynamic Elo strategy with provisional K-factor scaling (ADR-06).
    For N >= 2 teams, each team's expected score against every opponent team B is:
        E(A, B) = 1 / (1 + 10 ** ((R_B - R_A) / 400))
    where R_A is the mean rating of active players on team A, blended with the player's own rating.
    """

    def compute_team_base_points(
        self, team_scores: Mapping[str, int], policy: TenantPolicy
    ) -> Dict[str, int]:
        # Fallback team-level approximation when individual ratings are uniform
        return SimplePointsRatingStrategy().compute_team_base_points(team_scores, policy)

    def compute_player_deltas(
        self,
        participants: Sequence[ParticipantRatingInput],
        team_scores: Mapping[str, int],
        policy: TenantPolicy,
    ) -> Dict[int, int]:
        if not participants or len(team_scores) < 2:
            return {p.user_id: 0 for p in participants}

        # Compute mean rating per team
        team_ratings: Dict[str, list[int]] = {t: [] for t in team_scores}
        for p in participants:
            team_ratings.setdefault(p.team, []).append(p.current_rating or 100)

        team_avg: Dict[str, float] = {
            t: (sum(vals) / len(vals) if vals else 100.0)
            for t, vals in team_ratings.items()
        }

        teams = list(team_scores.keys())
        deltas: Dict[int, int] = {}

        for p in participants:
            if p.team not in team_scores:
                deltas[p.user_id] = 0
                continue

            my_score = team_scores[p.team]
            # Blend 50% team average rating + 50% player individual rating to prevent high-ELO farming
            effective_r = 0.5 * team_avg.get(p.team, float(p.current_rating)) + 0.5 * float(
                p.current_rating
            )

            opponents = [t for t in teams if t != p.team]
            if not opponents:
                deltas[p.user_id] = 0
                continue

            total_diff = 0.0
            for opp in opponents:
                opp_score = team_scores[opp]
                opp_r = team_avg.get(opp, 100.0)
                expected = 1.0 / (1.0 + 10.0 ** ((opp_r - effective_r) / 400.0))
                if my_score > opp_score:
                    actual = 1.0
                elif my_score == opp_score:
                    actual = 0.5
                else:
                    actual = 0.0
                total_diff += actual - expected

            mean_diff = total_diff / len(opponents)
            k_factor = (
                policy.elo_k_base
                if p.games_played < policy.elo_pro_games_threshold
                else policy.elo_k_pro
            )
            delta = round(k_factor * mean_diff)
            if p.is_mvp:
                delta += policy.rating_mvp_bonus
            deltas[p.user_id] = int(delta)

        return deltas


def resolve_rating_strategy(policy: TenantPolicy | None = None) -> IRatingStrategy:
    active_policy = policy or TenantPolicy()
    if active_policy.rating_system == RatingSystem.DYNAMIC_ELO.value:
        return DynamicEloRatingStrategy()
    return SimplePointsRatingStrategy()
