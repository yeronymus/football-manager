import pytest
from app.db.models import User, Position
from app.core.domain.balancer import (
    Player,
    BalanceBucket,
    get_bucket_for_position_str,
    get_bucket_for_position,
    balance_teams
)

# Helper function to generate mock Players
def create_mock_player(user_id: int, position: Position, rating: int = 100, alt_positions=None, full_name=None) -> Player:
    u = User(
        user_id=user_id,
        full_name=full_name or f"Player {user_id}",
        player_position=position,
        rating=rating,
        alt_positions=alt_positions or []
    )
    return Player(u)

def test_get_bucket_for_position_str():
    assert get_bucket_for_position_str("GK") == BalanceBucket.GK
    assert get_bucket_for_position_str("CB") == BalanceBucket.DEF
    assert get_bucket_for_position_str("CM") == BalanceBucket.MID
    assert get_bucket_for_position_str("ST") == BalanceBucket.FWD
    assert get_bucket_for_position_str("UNKNOWN") == BalanceBucket.MID

def test_get_bucket_for_position():
    assert get_bucket_for_position(Position.GK) == BalanceBucket.GK
    assert get_bucket_for_position(Position.CB) == BalanceBucket.DEF
    assert get_bucket_for_position(Position.CM) == BalanceBucket.MID
    assert get_bucket_for_position(Position.ST) == BalanceBucket.FWD

def test_balance_teams_empty():
    teams = balance_teams([], team_count=2)
    assert len(teams) == 2
    assert teams[0] == []
    assert teams[1] == []

def test_balance_teams_gk_priority():
    # 2 GKs, 4 Field players. 2 teams.
    players = [
        create_mock_player(1, Position.GK, 120),
        create_mock_player(2, Position.GK, 110),
        create_mock_player(3, Position.CM, 100),
        create_mock_player(4, Position.CB, 90),
        create_mock_player(5, Position.ST, 105),
        create_mock_player(6, Position.LB, 95)
    ]
    teams = balance_teams(players, team_count=2)

    # Each team should have 1 GK
    gks_team_0 = [p for p in teams[0] if get_bucket_for_position(p.position) == BalanceBucket.GK]
    gks_team_1 = [p for p in teams[1] if get_bucket_for_position(p.position) == BalanceBucket.GK]

    assert len(gks_team_0) == 1
    assert len(gks_team_1) == 1

    # Best GK goes to first team
    assert gks_team_0[0].id == 1
    assert gks_team_1[0].id == 2

def test_balance_teams_alt_gk_priority():
    # 1 Primary GK, 1 Alt GK, 4 Field players. 2 teams.
    players = [
        create_mock_player(1, Position.GK, 120),
        create_mock_player(2, Position.CM, 110, alt_positions=["GK"]),
        create_mock_player(3, Position.CM, 100),
        create_mock_player(4, Position.CB, 90),
        create_mock_player(5, Position.ST, 105),
        create_mock_player(6, Position.LB, 95)
    ]
    teams = balance_teams(players, team_count=2)

    # Check if Alt GK was assigned as GK for the second team
    # Note: balance_teams just puts them in the team list, it doesn't assign a role strictly in output,
    # but the algorithm handles GKs first. We just verify the teams are balanced in terms of these two players.

    # Team 1 gets the best GK (id 1)
    assert any(p.id == 1 for p in teams[0])
    # Team 2 gets the alt GK (id 2)
    assert any(p.id == 2 for p in teams[1])

def test_balance_teams_def_target():
    # 6 Defenders, 2 teams -> 3 per team
    players = [create_mock_player(i, Position.CB, 100 - i) for i in range(1, 7)]
    teams = balance_teams(players, team_count=2)

    assert len(teams[0]) == 3
    assert len(teams[1]) == 3

def test_balance_teams_rating_distribution():
    # 4 MIDs, check if ratings are balanced
    players = [
        create_mock_player(1, Position.CM, 150),
        create_mock_player(2, Position.CM, 140),
        create_mock_player(3, Position.CM, 130),
        create_mock_player(4, Position.CM, 120),
    ]
    teams = balance_teams(players, team_count=2)

    # distribute_list sorts descending (150, 140, 130, 120)
    # Team 0 gets 150. (Sums: T0=150, T1=0, Counts: T0=1, T1=0)
    # Team 1 gets 140. (Sums: T0=150, T1=140, Counts: T0=1, T1=1)
    # Team 1 gets 130. (Sums: T0=150, T1=270, Counts: T0=1, T1=2) -> WAIT:
    # Let's trace `teams.sort(key=lambda t: (len(t), sum(x.rating for x in t)))`
    # Initially: [[], []]
    # P1 (150): sorted: [[], []] -> adds to T0 -> T0=[150], T1=[]
    # P2 (140): sorted: [[], [150]] -> adds to T1 -> T0=[150], T1=[140]
    # P3 (130): sorted: [[140], [150]] -> adds to T1 -> T0=[150], T1=[140, 130] (len 2)
    # P4 (120): sorted: [[150], [140, 130]] -> adds to T0 -> T0=[150, 120], T1=[140, 130]

    sum0 = sum(p.rating for p in teams[0])
    sum1 = sum(p.rating for p in teams[1])

    # 150 + 120 = 270
    # 140 + 130 = 270
    assert sum0 == 270
    assert sum1 == 270

def test_balance_teams_odd_numbers():
    # 11 players
    players = [create_mock_player(i, Position.CM, 100) for i in range(1, 12)]
    teams = balance_teams(players, team_count=2)

    assert len(teams[0]) + len(teams[1]) == 11
    # One team should have 6, the other 5
    assert (len(teams[0]) == 6 and len(teams[1]) == 5) or (len(teams[0]) == 5 and len(teams[1]) == 6)

def test_balance_teams_3_teams():
    # 15 players, 3 teams. 3 GKs, 12 field players.
    players = [create_mock_player(i, Position.GK, 100) for i in range(1, 4)]
    players += [create_mock_player(i, Position.CM, 100) for i in range(4, 16)]

    teams = balance_teams(players, team_count=3)

    assert len(teams) == 3
    assert len(teams[0]) == 5
    assert len(teams[1]) == 5
    assert len(teams[2]) == 5

    # Each team has 1 GK
    for t in teams:
        assert len([p for p in t if get_bucket_for_position(p.position) == BalanceBucket.GK]) == 1

def test_balance_teams_no_gks():
    # 6 Field players, no GKs
    players = [create_mock_player(i, Position.CB, 100) for i in range(1, 7)]
    teams = balance_teams(players, team_count=2)
    assert len(teams[0]) == 3
    assert len(teams[1]) == 3

def test_balance_teams_too_many_gks():
    # 3 GKs for 2 teams. 1 team will get 2 GKs (one acting as field player)
    players = [create_mock_player(i, Position.GK, 100) for i in range(1, 4)]
    players += [create_mock_player(i, Position.CM, 100) for i in range(4, 11)] # 7 field players
    # Total 10 players -> 5 per team
    
    teams = balance_teams(players, team_count=2)
    assert len(teams[0]) == 5
    assert len(teams[1]) == 5
    
    # Total GKs should still be 3
    total_gks = sum(1 for t in teams for p in t if get_bucket_for_position(p.position) == BalanceBucket.GK)
    assert total_gks == 3

def test_balance_teams_extreme_ratings():
    # One very good player, many average
    players = [create_mock_player(1, Position.CM, 200)]
    players += [create_mock_player(i, Position.CM, 100) for i in range(2, 7)]
    # Total 6 players. T1: 200, 100, 100 = 400. T2: 100, 100, 100 = 300.
    # Distribute list: 200 -> T0. 100 -> T1. 100 -> T1. 100 -> T0. 100 -> T1. 100 -> T0.
    # T0: [200, 100, 100] = 400
    # T1: [100, 100, 100] = 300
    # Actually:
    # 200 -> T0 (T0:200, T1:0)
    # 100 -> T1 (T0:200, T1:100)
    # 100 -> T1 (T0:200, T1:200)
    # 100 -> T0 (T0:300, T1:200)
    # 100 -> T1 (T0:300, T1:300)
    # 100 -> T0 (T0:400, T1:300)
    
    teams = balance_teams(players, team_count=2)
    sum0 = sum(p.rating for p in teams[0])
    sum1 = sum(p.rating for p in teams[1])
    
    assert (sum0 == 400 and sum1 == 300) or (sum0 == 300 and sum1 == 400)
