import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from app.bot.admin_handlers import cmd_create

@pytest.mark.asyncio
async def test_cmd_create_delete_message_exception():
    message = MagicMock(spec=types.Message)

    chat = MagicMock(spec=types.Chat)
    chat.type = "group"
    message.chat = chat

    message.delete = AsyncMock(side_effect=TelegramBadRequest(method="deleteMessage", message="message to delete not found"))

    # This should not raise an exception, as it should be caught in the except block
    await cmd_create(message)
