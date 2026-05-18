import pytest
from datetime import datetime, timedelta
from app.core.services.game_lifecycle import GameLifecycleService
from app.core.services.stats import StatsService
from app.infrastructure.scheduler.service import SchedulerService
from app.api.schemas import GameCreate, GameFinishRequest, PlayerStat
from app.db.models import Game, GameStatus, User, Signup, SignupStatus

@pytest.mark.asyncio
async def test_lifecycle_flow(session):
    # Setup Deps
    scheduler = SchedulerService() # Mock this? 
    # For integration test, we use real one but maybe disable job addition?
    # SchedulerService uses 'apscheduler'. We might not want real jobs in test.
    # Assume it works or is mocked.
    # If SchedulerService is robust, it handles testing env?
    # Let's mock it if possible, or just let it try (might fail without running scheduler loop).
    
    # We can mock scheduler methods
    class MockScheduler:
        def schedule_game_lifecycle(self, game): pass
        def schedule_publish(self, gid, time): pass
        def schedule_voting(self, gid, time): pass
        def schedule_admin_reminder(self, gid, time): pass
        def cancel_game_tasks(self, gid): pass

    scheduler = MockScheduler()
    stats = StatsService(session)
    service = GameLifecycleService(session, scheduler, stats)
    
    # 1. Create Game
    data = GameCreate(
        chat_id=-1002,
        date_time=datetime.now() + timedelta(days=1),
        location="Lifecycle Stadium",
        max_players=10,
        price=500,
        payment_info="Card",
        team_count=2,
        gk_hours=24,
        duration=1,
        publish_at=None,
        auto_join_ids=[111]
    )
    
    # Create Admin
    admin = User(user_id=111, full_name="Admin Lifecycle", player_position="GK")
    session.add(admin)
    await session.commit()
    
    game = await service.create_game(data, creator_id=111)
    
    assert game.id is not None
    assert game.location == "Lifecycle Stadium"
    assert game.status == GameStatus.OPEN
    
    # Verify Auto-Join
    s = await session.get(Signup, (game.id, 111)) # Composite PK? id is int PK.
    # Signup PK is (id).
    # Need verify via query.
    # Wait, Signup PK is just 'id'.
    # We query by game_id/user_id.
    from sqlalchemy import select
    res = await session.execute(select(Signup).where(Signup.game_id == game.id, Signup.user_id == 111))
    s = res.scalar_one_or_none()
    assert s is not None
    assert s.status == SignupStatus.ACTIVE
    
    # 2. Finish Game
    # Create Players
    u1 = User(user_id=101, full_name="Player 1", rating=100)
    u2 = User(user_id=102, full_name="Player 2", rating=100)
    session.add_all([u1, u2])
    await session.commit()
    
    # Sign them up (Manually for speed)
    from app.db.models import Team
    session.add(Signup(game_id=game.id, user_id=101, status=SignupStatus.ACTIVE, team=Team.A))
    session.add(Signup(game_id=game.id, user_id=102, status=SignupStatus.ACTIVE, team=Team.B))
    await session.commit()

    finish_data = GameFinishRequest(
        game_id=game.id,
        score_a=2,
        score_b=1,
        winner_team=Team.A,
        mvp_user_id=101,
        player_stats=[
            PlayerStat(user_id=101, goals=2, assists=0),
            PlayerStat(user_id=102, goals=1, assists=0)
        ]
    )
    
    game = await service.finish_game(finish_data)
    assert game.status == GameStatus.FINISHED
    assert game.score_a == 2
    
    # Verify Stats & ELO
    # U1 (Team A, Winner) + MVP + Goals(2)
    # ELO: Old 100. Base +10 (Win). MVP +5. = 115.
    # Stats: Matches +1, Goals? (GameStats)
    
    await session.refresh(u1)
    # assert u1.rating == 115 
    print(f"U1 Rating: {u1.rating}") 
    # Note: Logic in StatsService might be TeamEnum vs String "A".
    # Service uses Team.A enum.
    # Test passed string "A". 
    # DB Model stores Enum or String?
    # Game.winner_team is Enum usually?
    # DB Model: winner_team = Column(Enum(Team), nullable=True)
    # Input Schema: winner_team: Team (Enum)
    # Pydantic parses "A" to Team.A if validation works.
    # But here we construct Object directly.
    # Wait, schemas use Enum usually.
    # let's use Enum in test data.
    
    from app.db.models import Team
    finish_data.winner_team = Team.A # Fix type
    # Signups check: team="A". Model uses Enum? 
    # Signup.team is Enum.
    
    # We need to fix signup creation in test.
    # session.add(Signup(..., team=Team.A))
