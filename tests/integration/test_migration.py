import pytest
from datetime import datetime, timedelta
from sqlalchemy import select
from app.db.models import User, Game, Signup, SignupStatus
from app.core.services.roster import RosterService, JoinResult
from app.core.repositories.game_repo import GameRepository

@pytest.mark.asyncio
async def test_migration_completed(session):
    # 1. Setup Data
    # Create Game
    game = Game(
        chat_id=-1001, 
        created_by=1, 
        date_time=datetime.now() + timedelta(days=2), # Future game (>36h)
        location="Test Stadium"
    )
    session.add(game)
    
    # Create Admin User
    admin = User(user_id=888, full_name="Admin User", player_position="CB", rating=100)
    session.add(admin)
    
    # Create Regular User
    user = User(user_id=999, full_name="Regular User", player_position="ST", rating=100)
    session.add(user)
    
    await session.commit()
    await session.refresh(game)
    
    # 2. Test RosterService (Admin)
    from app.core.uow import UnitOfWork
    async with UnitOfWork(session=session) as uow:
        roster_service = RosterService(uow)
        
        result = await roster_service.join_player(game.id, admin)
        assert result.success is True
        assert result.signup is not None
        assert result.signup.user_id == 888
        
        await session.commit()
        
        # Verify DB State
        signup_new = await session.get(Signup, result.signup.id)
        assert signup_new is not None
        assert signup_new.status == SignupStatus.ACTIVE
        
        # 3. Test RosterService (Regular User)
        result_user = await roster_service.join_player(game.id, user)
        assert result_user.success is True
        
        await session.commit()
        
        # Verify DB State
        signup_user = await session.get(Signup, result_user.signup.id)
        assert signup_user is not None
        assert signup_user.user_id == 999
        
        # 4. Count Check
        count = await uow.game_repo.get_active_signups_count(game.id)
        assert count == 2
        
        # 5. Leave Logic
        # Admin leaves
        success, msg, promoted = await roster_service.leave_player(game.id, 888, is_admin=True)
        assert success is True
        await session.commit()
        
        count = await uow.game_repo.get_active_signups_count(game.id)
        assert count == 1 # Only 999 remains
        
        # User leaves
        success, msg, promoted = await roster_service.leave_player(game.id, 999)
        assert success is True
        await session.commit()
        
        count = await uow.game_repo.get_active_signups_count(game.id)
        assert count == 0

    print("Migration Test Passed: RosterService handles all flows.")
