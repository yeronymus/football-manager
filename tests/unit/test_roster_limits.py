import asyncio
import pytest
from datetime import datetime, timedelta
from app.core.services.roster import RosterService, JoinResult, SignupStatus
from app.db.models import Game, GameStatus, User, Signup

# Simple Mock Objects
class MockRepo:
    def __init__(self):
        self.games = {}
        self.signups = []
        
    async def get_with_lock(self, game_id):
        return self.games.get(game_id)
        
    async def get_signup(self, game_id, user_id):
        for s in self.signups:
            if s.game_id == game_id and s.user_id == user_id:
                return s
        return None
        
    async def get_active_signups_count(self, game_id):
         return len([s for s in self.signups if s.game_id == game_id and s.status == SignupStatus.ACTIVE])
         
    def create_signup(self, gid, uid, status):
         s = Signup(game_id=gid, user_id=uid, status=status)
         self.signups.append(s)
         return s

class MockUOW:
    def __init__(self):
        self.game_repo = MockRepo()
        self.session = None

async def _run_async_tests():
    # Setup
    uow = MockUOW()
    service = RosterService(uow)
    
    # User
    user = User(user_id=1, full_name="Test User", player_position="MID")
    
    # Case 1: Unlimited Window (0)
    g1 = Game(id=1, status=GameStatus.OPEN, max_players=10, registration_hours=0, gk_hours=48)
    g1.created_at = datetime.now() - timedelta(hours=25) 
    g1.date_time = datetime.now() + timedelta(hours=10) 
    uow.game_repo.games[1] = g1
    
    res = await service.join_player(1, user)
    assert res.success is True
    assert "записаны" in res.message.lower()

    # Case 2: 24h Window - EXPIRED
    g2 = Game(id=2, status=GameStatus.OPEN, max_players=10, registration_hours=24, gk_hours=48)
    g2.created_at = datetime.now() - timedelta(hours=25) 
    g2.date_time = datetime.now() + timedelta(hours=10)
    uow.game_repo.games[2] = g2
    
    res = await service.join_player(2, user)
    assert res.success is False
    assert "запись закрыта" in res.message.lower()
    
    # Case 3: 24h Window - VALID
    g3 = Game(id=3, status=GameStatus.OPEN, max_players=10, registration_hours=24, gk_hours=48)
    g3.created_at = datetime.now() - timedelta(hours=23) 
    g3.date_time = datetime.now() + timedelta(hours=10)
    uow.game_repo.games[3] = g3
    
    res = await service.join_player(3, user, ignore_limit=False)
    assert res.success is True
    
    # Case 4: Max Players (Active vs Reserve)
    g4 = Game(id=4, status=GameStatus.OPEN, max_players=1, registration_hours=0, gk_hours=48)
    g4.date_time = datetime.now() + timedelta(hours=10)
    g4.created_at = datetime.now() 
    uow.game_repo.games[4] = g4
    
    # Fill with another user
    uow.game_repo.signups.append(Signup(game_id=4, user_id=999, status=SignupStatus.ACTIVE))
    
    res = await service.join_player(4, user)
    assert res.success is True
    assert res.is_reserve is True
    
    # Case 5: 999 Players (Unlimited)
    g5 = Game(id=5, status=GameStatus.OPEN, max_players=999, registration_hours=0, gk_hours=48)
    g5.date_time = datetime.now() + timedelta(hours=10)
    g5.created_at = datetime.now()
    uow.game_repo.games[5] = g5
    
    # Add 20 players
    for i in range(20):
         uow.game_repo.signups.append(Signup(game_id=5, user_id=100+i, status=SignupStatus.ACTIVE))

    res = await service.join_player(5, user)
    assert res.success is True
    assert res.is_reserve is False

def test_roster_limits_sync_wrapper():
    """
    Synchronous wrapper to run async tests. 
    Avoids pytest-asyncio environment issues by managing its own loop.
    """
    asyncio.run(_run_async_tests())
