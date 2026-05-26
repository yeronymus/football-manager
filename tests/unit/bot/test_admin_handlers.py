
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from app.bot.handlers.admin_handlers import cmd_create

@pytest.mark.asyncio
async def test_cmd_create_delete_message_exception():
    message = MagicMock(spec=types.Message)

    chat = MagicMock(spec=types.Chat)
    chat.type = "group"
    message.chat = chat

    message.delete = AsyncMock(side_effect=TelegramBadRequest(method="deleteMessage", message="message to delete not found"))

    # This should not raise an exception, as it should be caught in the except block
    await cmd_create(message)
    assert message.delete.called

@pytest.mark.asyncio
async def test_cmd_create_in_private_chat():
    message = MagicMock()
    
    message.chat.type = "private"
    message.from_user.id = 12345
    message.answer = AsyncMock()
    
    from app.config import settings
    with MagicMock() as mock_settings:
        # Instead of patching settings object, we can patch the module level access if needed,
        # but let's try to patch settings directly where it's used.
        # Actually, cmd_create uses settings from app.config
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("app.bot.handlers.admin_handlers.settings.admin_ids", [12345])
            mp.setattr("app.bot.handlers.admin_handlers.settings.system_owner_id", 0)
            mp.setattr("app.bot.handlers.admin_handlers.settings.webapp_url", "https://test.com")
            
            await cmd_create(message)
            
            # Verify it answered
            assert message.answer.called

@pytest.mark.asyncio
async def test_cmd_republish():
    from app.bot.handlers.admin_handlers import cmd_republish
    message = MagicMock()
    message.chat.type = "private"
    message.from_user.id = 12345
    message.text = "/republish 17"
    message.answer = AsyncMock()
    
    session = AsyncMock()
    
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("app.bot.handlers.admin_handlers.settings.admin_ids", [12345])
        mp.setattr("app.bot.handlers.admin_handlers.settings.system_owner_id", 0)
        
        mock_publish_task = AsyncMock()
        mp.setattr("app.scheduler.tasks.publish_game_task", mock_publish_task)
        
        await cmd_republish(message, session)
        
        assert mock_publish_task.called
        assert message.answer.called
        assert "успешно переопубликована" in message.answer.call_args[0][0]
