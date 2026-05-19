import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from app.config import settings
from aiogram import types
import logging

# Configure logging
logging.basicConfig(level=logging.ERROR)

class TestStranglerRouter(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_routing(self):
        """Test that Game ID <= 5 routes to legacy handler"""
        settings.last_legacy_game_id = 5
        
        # Mock callback
        callback = AsyncMock(spec=types.CallbackQuery)
        callback.data = "join_5"
        callback.from_user = MagicMock()
        callback.from_user.id = 12345
        
        # Patch the handlers
        with patch('app.bot.game_handlers.process_join') as mock_new_handler, \
             patch('app.bot.legacy_handlers.process_join', new_callable=AsyncMock) as mock_legacy_handler:
            
            # Since we can't easily import `process_join` if it imports `UnitOfWork` which fails without DB
            # We will instead import the function under test inside the patch context
            # or mock the dependencies of game_handlers.py
            
            from app.bot.game_handlers import process_join
            
            # Execute
            await process_join(callback)
            
            # Verify
            mock_legacy_handler.assert_called_once()
            # New logic (UnitOfWork, RosterService) should NOT be called
            # But process_join itself IS the function we called.
            # Wait, process_join calls legacy_join internally.
            # So we need to patch `app.bot.legacy_handlers.process_join`.
            
    async def test_new_architecture_routing(self):
        """Test that Game ID > 5 routes to new architecture"""
        settings.last_legacy_game_id = 5
        
        callback = AsyncMock(spec=types.CallbackQuery)
        callback.data = "join_6"
        callback.from_user = MagicMock()
        callback.from_user.id = 12345
        
        # Patch Legacy Handler to ensure it's NOT called
        with patch('app.bot.legacy_handlers.process_join', new_callable=AsyncMock) as mock_legacy_handler, \
             patch('app.core.uow.UnitOfWork') as mock_uow_cls, \
             patch('app.core.services.roster.RosterService') as mock_service_cls:
            
            # Mock UOW context manager
            mock_uow = AsyncMock()
            mock_uow_cls.return_value.__aenter__.return_value = mock_uow
            
            # Mock Repo
            mock_uow.user_repo.get_by_id = AsyncMock(return_value=MagicMock(user_id=12345))
            
            # Mock Service
            mock_service = list(mock_service_cls.side_effect)[0] if mock_service_cls.side_effect else mock_service_cls.return_value
            # Wait, constructing service: RosterService(uow)
            mock_service = mock_service_cls.return_value
            mock_service.join_player = AsyncMock(return_value=MagicMock(success=True, signup=True))
            
            from app.bot.game_handlers import process_join
            
            await process_join(callback)
            
            # Verify Legacy NOT called
            mock_legacy_handler.assert_not_called()
            
            # Verify New Service CALLED
            mock_service_cls.assert_called_once()
            mock_service.join_player.assert_called_once()

if __name__ == "__main__":
    unittest.main()
