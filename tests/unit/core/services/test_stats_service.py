import pytest
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.services.stats import StatsService
from app.db.models import Game, User, Signup, SignupStatus, Team, PlayerProfile, RatingHistory, GameStats, GameStatus, GameType, Chat, Position

@pytest.mark.asyncio
async def test_apply_game_results_two_teams(session: AsyncSession):
    stats_service = StatsService(session)

    # 1. Setup Chat, Game, Users
    chat = Chat(chat_id=-1001, title="Prague Football")
    session.add(chat)
    await session.commit()

    game = Game(
        id=1,
        chat_id=chat.chat_id,
        created_by=1,
        date_time=datetime.now(),
        location="Strahov",
        max_players=10,
        status=GameStatus.FINISHED,
        game_type=GameType.REGULAR,
        team_count=2,
        score_a=3,
        score_b=1
    )
    session.add(game)
    await session.commit()

    # Create 4 players: p1, p2 (Team A), p3, p4 (Team B)
    p1 = User(user_id=101, username="p1", full_name="Player 1", player_position=Position.MID, alt_positions=[], games_played=0, stats_matches=0, stats_mvp=0)
    p2 = User(user_id=102, username="p2", full_name="Player 2", player_position=Position.MID, alt_positions=[], games_played=0, stats_matches=0, stats_mvp=0)
    p3 = User(user_id=103, username="p3", full_name="Player 3", player_position=Position.MID, alt_positions=[], games_played=0, stats_matches=0, stats_mvp=0)
    p4 = User(user_id=104, username="p4", full_name="Player 4", player_position=Position.MID, alt_positions=[], games_played=0, stats_matches=0, stats_mvp=0)
    session.add_all([p1, p2, p3, p4])
    await session.commit()

    # Profiles
    profile1 = PlayerProfile(user_id=p1.user_id, chat_id=chat.chat_id, rating=100, games_played=0, stats_matches=0)
    profile2 = PlayerProfile(user_id=p2.user_id, chat_id=chat.chat_id, rating=100, games_played=0, stats_matches=0)
    profile3 = PlayerProfile(user_id=p3.user_id, chat_id=chat.chat_id, rating=100, games_played=0, stats_matches=0)
    profile4 = PlayerProfile(user_id=p4.user_id, chat_id=chat.chat_id, rating=100, games_played=0, stats_matches=0)
    session.add_all([profile1, profile2, profile3, profile4])
    await session.commit()

    # Signups
    s1 = Signup(game_id=game.id, user_id=p1.user_id, team=Team.A, status=SignupStatus.ACTIVE)
    s2 = Signup(game_id=game.id, user_id=p2.user_id, team=Team.A, status=SignupStatus.ACTIVE)
    s3 = Signup(game_id=game.id, user_id=p3.user_id, team=Team.B, status=SignupStatus.ACTIVE)
    s4 = Signup(game_id=game.id, user_id=p4.user_id, team=Team.B, status=SignupStatus.ACTIVE)
    session.add_all([s1, s2, s3, s4])
    await session.commit()

    # P1 is MVP
    await stats_service.apply_game_results(game, mvp_ids={p1.user_id})
    await session.commit()

    # Assert changes
    await session.refresh(profile1)
    await session.refresh(profile2)
    await session.refresh(profile3)
    await session.refresh(profile4)

    await session.refresh(p1)
    await session.refresh(p2)
    await session.refresh(p3)

    # Team A won: +10 points base.
    # P1 got MVP (+5 points) -> +15 points. Rating: 115
    assert profile1.rating == 115
    assert profile1.games_played == 1
    assert p1.stats_mvp == 1

    # P2 just won -> +10 points. Rating: 110
    assert profile2.rating == 110
    assert profile2.games_played == 1

    # Team B lost: -5 points base -> Rating: 95
    assert profile3.rating == 95
    assert profile4.rating == 95

    # Check histories
    histories_res = await session.execute(select(RatingHistory).where(RatingHistory.game_id == game.id))
    histories = histories_res.scalars().all()
    assert len(histories) == 4


@pytest.mark.asyncio
async def test_apply_game_results_three_teams(session: AsyncSession):
    stats_service = StatsService(session)

    # 1. Setup Chat, Game, Users
    chat = Chat(chat_id=-1002, title="Three Team Tourney")
    session.add(chat)
    await session.commit()

    game = Game(
        id=2,
        chat_id=chat.chat_id,
        created_by=1,
        date_time=datetime.now(),
        location="Praha",
        max_players=18,
        status=GameStatus.FINISHED,
        game_type=GameType.REGULAR,
        team_count=3,
        score_a=5,
        score_b=5,
        score_c=2
    )
    session.add(game)
    await session.commit()

    # 6 players: p1, p2 (A), p3, p4 (B), p5, p6 (C)
    users = []
    profiles = []
    signups = []
    for i in range(1, 7):
        user_id = 200 + i
        user = User(user_id=user_id, username=f"p{i}", full_name=f"Player {i}", player_position=Position.MID, alt_positions=[])
        profile = PlayerProfile(user_id=user_id, chat_id=chat.chat_id, rating=100)
        team = Team.A if i <= 2 else (Team.B if i <= 4 else Team.C)
        signup = Signup(game_id=game.id, user_id=user_id, team=team, status=SignupStatus.ACTIVE)
        users.append(user)
        profiles.append(profile)
        signups.append(signup)

    session.add_all(users + profiles + signups)
    await session.commit()

    await stats_service.apply_game_results(game, mvp_ids=set())
    await session.commit()

    # Team A & B tied for 1st place -> unique scores: [5, 2]
    # Rank 0 score 5: points = 10
    # Rank 1 score 2: points = -5
    for p in profiles:
        await session.refresh(p)

    # Team A and B should get +10 points
    assert profiles[0].rating == 110 # A
    assert profiles[2].rating == 110 # B

    # Team C should get -5 points
    assert profiles[4].rating == 95 # C


@pytest.mark.asyncio
async def test_revert_stats(session: AsyncSession):
    stats_service = StatsService(session)

    chat = Chat(chat_id=-1003, title="Revert Test")
    session.add(chat)
    await session.commit()

    game = Game(
        id=3,
        chat_id=chat.chat_id,
        created_by=1,
        date_time=datetime.now(),
        location="Praha",
        max_players=10,
        status=GameStatus.FINISHED,
        game_type=GameType.REGULAR,
        team_count=2,
        score_a=2,
        score_b=0
    )
    session.add(game)
    await session.commit()

    p1 = User(user_id=301, username="p1", full_name="Player 1", player_position=Position.MID, alt_positions=[], games_played=0, stats_matches=0, stats_mvp=0)
    p2 = User(user_id=302, username="p2", full_name="Player 2", player_position=Position.MID, alt_positions=[], games_played=0, stats_matches=0, stats_mvp=0)
    session.add_all([p1, p2])
    await session.commit()

    profile1 = PlayerProfile(user_id=301, chat_id=chat.chat_id, rating=100, games_played=0, stats_matches=0)
    profile2 = PlayerProfile(user_id=302, chat_id=chat.chat_id, rating=100, games_played=0, stats_matches=0)
    session.add_all([profile1, profile2])
    await session.commit()

    s1 = Signup(game_id=game.id, user_id=301, team=Team.A, status=SignupStatus.ACTIVE)
    s2 = Signup(game_id=game.id, user_id=302, team=Team.B, status=SignupStatus.ACTIVE)
    session.add_all([s1, s2])
    await session.commit()

    # Apply results, with p1 as MVP
    await stats_service.apply_game_results(game, mvp_ids={301})
    
    # Save GameStats MVP (as revert_stats retrieves GameStats too)
    gs1 = GameStats(game_id=game.id, user_id=301, is_mvp=True, goals=0)
    gs2 = GameStats(game_id=game.id, user_id=302, is_mvp=False, goals=0)
    session.add_all([gs1, gs2])
    await session.commit()

    # Revert Stats
    await stats_service.revert_stats(game.id)
    await session.commit()

    # Assert ratings reverted
    await session.refresh(profile1)
    await session.refresh(profile2)
    await session.refresh(p1)
    await session.refresh(p2)

    assert profile1.rating == 100
    assert profile1.games_played == 0
    assert p1.stats_mvp == 0

    assert profile2.rating == 100
    assert profile2.games_played == 0

    # Ensure histories deleted
    hist_res = await session.execute(select(RatingHistory).where(RatingHistory.game_id == game.id))
    assert len(hist_res.scalars().all()) == 0
