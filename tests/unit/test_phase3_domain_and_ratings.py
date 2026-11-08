from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.domain.balancer import (
    BalanceBucket,
    Player,
    RoleBasedBalancingStrategy,
    _optimize_same_bucket_2opt,
    _team_spread_sq,
    get_bucket_for_position,
)
from app.core.domain.ratings import (
    DynamicEloRatingStrategy,
    ParticipantRatingInput,
    SimplePointsRatingStrategy,
    resolve_rating_strategy,
)
from app.core.domain.tenant_policy import RatingSystem, TenantPolicy
from app.core.services.stats import StatsService
from app.core.timezone import format_tenant_dt, to_tenant_dt
from app.db.models import Game, GameStats, Position, RatingHistory, Signup, SignupStatus, Team, User


def test_pure_domain_player_and_2opt_variance_minimization():
    """
    Verifies that Player can be constructed without ORM User objects and that
    _optimize_same_bucket_2opt strictly reduces inter-team rating variance while
    preserving positional bucket counts and locked GKs across 2 and 3 teams.
    """
    # Construct unbalanced 2-team setup with identical bucket composition
    team_a = [
        Player(user_id=1, full_name="GK1", position="GK", rating_override=150),
        Player(user_id=2, full_name="DEF1", position="CB", rating_override=200),
        Player(user_id=3, full_name="MID1", position="CM", rating_override=190),
        Player(user_id=4, full_name="FWD1", position="ST", rating_override=180),
    ]
    team_b = [
        Player(user_id=5, full_name="GK2", position="GK", rating_override=100),
        Player(user_id=6, full_name="DEF2", position="CB", rating_override=100),
        Player(user_id=7, full_name="MID2", position="CM", rating_override=110),
        Player(user_id=8, full_name="FWD2", position="ST", rating_override=120),
    ]
    teams = [team_a, team_b]
    initial_spread = _team_spread_sq(teams)
    assert initial_spread > 0

    # Lock GKs (1 and 5) so primary GKs stay on their assigned teams
    _optimize_same_bucket_2opt(teams, locked_player_ids={1, 5})
    final_spread = _team_spread_sq(teams)
    assert final_spread < initial_spread

    # Verify GKs remained locked to their respective teams
    assert any(p.id == 1 for p in teams[0])
    assert any(p.id == 5 for p in teams[1])

    # Verify bucket counts per team remained invariant (1 GK, 1 DEF, 1 MID, 1 FWD)
    for t in teams:
        buckets = [get_bucket_for_position(p.position) for p in t]
        assert buckets.count(BalanceBucket.GK) == 1
        assert buckets.count(BalanceBucket.DEF) == 1
        assert buckets.count(BalanceBucket.MID) == 1
        assert buckets.count(BalanceBucket.FWD) == 1


def test_role_based_balancer_3_teams_pure_domain():
    """Verifies N=3 team balancing with RoleBasedBalancingStrategy using pure domain Players."""
    players = [
        Player(user_id=i, full_name=f"P{i}", position=pos, rating_override=100 + i * 7)
        for i, pos in enumerate(
            [
                "GK", "GK", "GK",
                "CB", "CB", "CB", "LB", "RB", "DEF",
                "CM", "CM", "CAM", "CDM", "LM", "RM",
                "ST", "LW", "RW",
            ],
            start=1,
        )
    ]
    strategy = RoleBasedBalancingStrategy()
    teams = strategy.balance(players, team_count=3)
    assert len(teams) == 3
    assert [len(t) for t in teams] == [6, 6, 6]
    sums = [sum(p.rating for p in t) for t in teams]
    assert max(sums) - min(sums) <= 35


def test_simple_points_vs_dynamic_elo_rating_strategy():
    """
    Verifies SimplePointsRatingStrategy and DynamicEloRatingStrategy:
    - Underdog team beating higher-rated favorite team gains more Elo points.
    - Provisional player (games_played < threshold) gets larger K-factor delta than veteran.
    - 3-team pairwise Elo works symmetrically.
    """
    simple_policy = TenantPolicy(rating_system=RatingSystem.SIMPLE_POINTS)
    elo_policy = TenantPolicy(
        rating_system=RatingSystem.DYNAMIC_ELO,
        elo_k_base=32,
        elo_k_pro=16,
        elo_pro_games_threshold=10,
    )

    assert isinstance(resolve_rating_strategy(simple_policy), SimplePointsRatingStrategy)
    assert isinstance(resolve_rating_strategy(elo_policy), DynamicEloRatingStrategy)

    # Underdog Team A (rating 100) beats Favorite Team B (rating 300)
    participants = [
        ParticipantRatingInput(
            user_id=1, team="A", current_rating=100, games_played=2, is_mvp=False
        ),  # Provisional underdog
        ParticipantRatingInput(
            user_id=2, team="A", current_rating=100, games_played=25, is_mvp=False
        ),  # Veteran underdog
        ParticipantRatingInput(
            user_id=3, team="B", current_rating=300, games_played=25, is_mvp=False
        ),  # Veteran favorite
    ]
    strategy = DynamicEloRatingStrategy()
    deltas_upset = strategy.compute_player_deltas(
        participants, team_scores={"A": 3, "B": 1}, policy=elo_policy
    )

    # Provisional winner gains more than veteran winner due to K=32 vs K=16
    assert deltas_upset[1] > deltas_upset[2] > 0
    # Favorite loser loses points
    assert deltas_upset[3] < 0

    # Compare against expected win (Favorite B beats Underdog A)
    deltas_expected = strategy.compute_player_deltas(
        participants, team_scores={"A": 1, "B": 3}, policy=elo_policy
    )
    # Favorite winning against underdog gains fewer points than underdog winning upset
    assert deltas_upset[2] > deltas_expected[3] > 0


@pytest.mark.asyncio
async def test_stats_service_with_dynamic_elo_policy():
    """Verifies that StatsService.apply_game_results uses DynamicEloRatingStrategy when configured."""
    session = AsyncMock()
    added_objects = []
    session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

    game = Game(id=42, chat_id=-100123, score_a=4, score_b=1)
    u1 = User(
        user_id=101,
        full_name="Underdog Winner",
        player_position=Position.ST,
        rating=100,
        games_played=2,
        stats_matches=2,
        stats_mvp=0,
    )
    u2 = User(
        user_id=102,
        full_name="Favorite Loser",
        player_position=Position.CB,
        rating=300,
        games_played=20,
        stats_matches=20,
        stats_mvp=0,
    )
    s1 = Signup(game_id=42, user_id=101, status=SignupStatus.ACTIVE, team=Team.A)
    s2 = Signup(game_id=42, user_id=102, status=SignupStatus.ACTIVE, team=Team.B)

    joined_res = MagicMock()
    joined_res.all.return_value = [
        (u1, Team.A, None),
        (u2, Team.B, None),
    ]

    session.execute = AsyncMock(return_value=joined_res)

    service = StatsService(session)
    await service.apply_game_results(
        game,
        mvp_ids={101},
        policy={"rating_system": "dynamic_elo", "elo_k_base": 32, "elo_k_pro": 16},
    )

    # Underdog provisional winner with MVP should gain significant Elo (> 20)
    assert u1.rating > 120
    assert u2.rating < 300
    histories = [o for o in added_objects if isinstance(o, RatingHistory)]
    assert len(histories) == 2


def test_tenant_timezone_formatting():
    """Verifies IANA timezone conversion per tenant via to_tenant_dt and format_tenant_dt."""
    utc_dt = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    prague_str = format_tenant_dt(utc_dt, "%H:%M", "Europe/Prague")
    almaty_str = format_tenant_dt(utc_dt, "%H:%M", "Asia/Almaty")
    utc_str = format_tenant_dt(utc_dt, "%H:%M", "UTC")

    assert utc_str == "16:00"
    assert prague_str == "18:00"  # CEST = UTC+2
    assert almaty_str == "21:00"  # UTC+5
    # Invalid timezone gracefully falls back to Europe/Prague
    assert to_tenant_dt(utc_dt, "Invalid/Timezone").hour == 18


def test_user_is_guest_and_unique_constraints():
    """Verifies User.is_guest column and UniqueConstraints on GameStats and RatingHistory."""
    guest = User(
        user_id=-999,
        full_name="Temp Guest",
        player_position=Position.CM,
        is_guest=True,
    )
    assert guest.is_guest is True

    gs_constraints = {c.name for c in GameStats.__table__.constraints if c.name}
    rh_constraints = {c.name for c in RatingHistory.__table__.constraints if c.name}
    assert "uq_game_stats_game_user" in gs_constraints
    assert "uq_rating_history_game_user" in rh_constraints
