import asyncio
import sys
import os
from sqlalchemy import select

# Use Production Credentials to test against actual DB state (via tunnel if possible, or assume local env matches prod if we pulled data)
# Actually, I can't connect to prod DB easily from here without the tunnel which I don't have.
# But I can check the CODE logic. 
# The issue is likely data-dependent.
# I will use the local DB which I might have populated? 
# No, local DB is likely empty or different.
# I will create a unit test style script that MOCKS the DB state to reproduce "Signup Closed" 
# given the known state of Game 5 (Open).

# Wait, if Game 5 is OPEN, why would it fail?
# RosterService.join_player:
# if game.status != OPEN or ACTIVE -> "Запись закрыта"
# valid_until = game.date_time - timedelta(hours=game.gk_hours) # Wait, logic might be time based?
# code:
# if datetime.now() > game.date_time: "Игра уже прошла"

sys.path.append(os.getcwd())
try:
    from app.core.services.roster import RosterService, JoinResult
    from app.db.models import Game, GameStatus, User, Position
    from datetime import datetime, timedelta, timezone
except ImportError:
    # Setup path
    sys.path.append("/home/yeronym/Documents/fmBot/football-manager")
    from app.core.services.roster import RosterService, JoinResult
    from app.db.models import Game, GameStatus, User, Position

# Mock Settings
from unittest.mock import MagicMock
import app.config
app.config.settings = MagicMock()
app.config.settings.start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
app.config.settings.last_legacy_game_id = 4 # Assume 5 is new
app.config.settings.admin_ids = [502389915]

# Mock UnitOfWork and Repos
class MockRepo:
    async def get_by_id(self, id):
        if id == 123:
            return User(user_id=123, full_name="Test User", player_position=Position.FWD)
        return None
    
    async def get_game(self, id):
        if id == 5:
            return Game(
                id=5, 
                chat_id=-1001234567890,
                status=GameStatus.OPEN, 
                date_time=datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc),
                max_players=18,
                gk_hours=48,
                price=100,
                team_count=2,
                has_active_gk_a=True,
                has_active_gk_b=True
            )
        return None
        
    async def get_signups(self, game_id):
        return []
        
    async def get_signup(self, game_id, user_id):
        return None
    
    # Add other needed methods that might be called
    async def get_count(self, game_id, status):
        return 0
        
    async def get_rating_history(self, user_id):
        return []
    
    async def get_active_signups_count(self, game_id):
        return 0
        
    async def get_active_players(self, game_id):
        return []
        
    async def get_with_lock(self, game_id):
        return await self.get_game(game_id)
        
    async def create_signup(self, game_id, user_id, status):
        print(f"DEBUG: Creating signup for user {user_id} with status {status}")
        return Signup(id=999, game_id=game_id, user_id=user_id, status=status)

class MockUoW:
    def __init__(self):
        self.user_repo = MockRepo()
        self.game_repo = MockRepo()
        # Add get_game_stats to game_repo if that is where it is called
        self.game_repo.get_game_stats = self.game_repo.get_game_stats 
        
        self.signup_repo = MockRepo()
        self.stats_repo = MockRepo() # For rating history if needed
        self.rating_repo = MockRepo() # Assuming rating history is here
        self.session = None # Mock session
    
    async def __aenter__(self): 
        return self
    async def __aexit__(self, *args): 
        pass
    async def commit(self): 
        pass
    async def rollback(self):
        pass

async def test_join():
    uow = MockUoW()
    service = RosterService(uow)
    
    print("Testing Join for Game 5 (Status=OPEN, Date=Feb 14)...")
    try:
        user = await uow.user_repo.get_by_id(123)
        result = await service.join_player(5, user)
        print(f"Result: Success={result.success}, Message='{result.message}'")
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_join())
