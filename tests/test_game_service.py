import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import asyncio
from app.services.game_service import GameService, GameActionError, AlreadySignedUpError, CancellationLockedError
from app.db.models import Game, User, Signup, SignupStatus, GameStatus, Position
from app.api.schemas import GameUpdate

class TestGameService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        # configure execute to return a MagicMock (which acts as the Result object) when awaited
        self.session.execute.return_value = MagicMock()
        self.service = GameService(self.session)
        
    async def test_join_game_success(self):
        # Setup
        game = Game(id=1, status=GameStatus.OPEN, max_players=10, created_at=datetime.now(), gk_hours=0)
        user = User(user_id=123, full_name="Test User", player_position=Position.CM)
        
        # Mock Session
        self.session.execute.return_value.scalar_one_or_none.side_effect = [
            game, # Game lock
            None  # Existing signup
        ]
        self.session.get.return_value = user # User fetch
        self.session.execute.return_value.scalar.return_value = 5 # Active count
        
        # Execute
        signup, msg = await self.service.join_game(1, 123)
        
        # Verify
        self.assertIsInstance(signup, Signup)
        self.assertEqual(signup.status, SignupStatus.ACTIVE)
        self.session.add.assert_called_once()
        self.session.commit.assert_called_once()

    async def test_join_game_duplicate(self):
        game = Game(id=1, status=GameStatus.OPEN)
        signup = Signup(user_id=123, game_id=1)
        
        self.session.execute.return_value.scalar_one_or_none.side_effect = [
            game, 
            signup 
        ]
        
        with self.assertRaises(AlreadySignedUpError):
            await self.service.join_game(1, 123)

    async def test_join_gk_priority(self):
        # 48h active, user is CM, 2 slots left
        game = Game(id=1, status=GameStatus.OPEN, max_players=10, created_at=datetime.now(), gk_hours=48)
        user = User(user_id=123, full_name="Field Player", player_position=Position.CM)
        
        self.session.execute.return_value.scalar_one_or_none.side_effect = [game, None]
        self.session.get.return_value = user
        self.session.execute.return_value.scalar.return_value = 8 # 2 slots left
        
        signup, msg = await self.service.join_game(1, 123)
        
        self.assertEqual(signup.status, SignupStatus.RESERVE)
        self.assertIn("резерве", msg)

    async def test_leave_game_success(self):
        signup = Signup(user_id=123, game_id=1, status=SignupStatus.ACTIVE)
        game = Game(id=1, status=GameStatus.OPEN, date_time=datetime.now() + timedelta(hours=48)) # Far future
        
        self.session.execute.return_value.scalar_one_or_none.side_effect = [
            signup, # Signup fetch
            game,   # Game fetch for lock check
            None    # Reserve fetch (empty)
        ]
        
        returned_game, was_active = await self.service.leave_game(1, 123)
        
        self.assertTrue(was_active)
        self.session.delete.assert_called_with(signup)

    async def test_leave_game_locked(self):
        signup = Signup(user_id=123, game_id=1, status=SignupStatus.ACTIVE)
        game = Game(id=1, date_time=datetime.now() + timedelta(hours=10)) # < 36h
        
        self.session.execute.return_value.scalar_one_or_none.side_effect = [signup, game]
        
        with self.assertRaises(CancellationLockedError):
            await self.service.leave_game(1, 123)

    @patch("app.services.game_service.GameService.get_game")
    async def test_update_game(self, mock_get_game):
        game = Game(id=1, location="Old Loc", chat_id=100)
        self.service.get_game = AsyncMock(return_value=game)
        
        update = GameUpdate(game_id=1, location="New Loc", initData="test")
        
        with patch("app.bot.main.bot.send_message", new_callable=AsyncMock) as mock_send:
             updated = await self.service.update_game(update)
             
             self.assertEqual(updated.location, "New Loc")
             mock_send.assert_called() # Check notification sent

if __name__ == "__main__":
    unittest.main()
