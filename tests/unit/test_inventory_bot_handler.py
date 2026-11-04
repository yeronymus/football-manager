import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types
from app.bot.handlers.admin_handlers import cmd_inventory, cmd_dashboard
from app.db.models import Chat, InventoryItem, InventoryCategory, InventoryStatus

@pytest.mark.asyncio
async def test_cmd_inventory_in_group_deleted():
    # Strict rule: NEVER process commands in groups! Must delete message and return.
    message = MagicMock(spec=types.Message)
    message.chat = MagicMock(spec=types.Chat)
    message.chat.type = "group"
    message.chat.id = -1001234567
    message.delete = AsyncMock()
    message.answer = AsyncMock()
    session = AsyncMock()

    await cmd_inventory(message, session)

    assert message.delete.called
    assert not message.answer.called

@pytest.mark.asyncio
async def test_cmd_inventory_with_items_private():
    message = MagicMock(spec=types.Message)
    message.chat = MagicMock(spec=types.Chat)
    message.chat.type = "private"
    message.chat.id = 12345
    message.from_user = MagicMock(spec=types.User)
    message.from_user.id = 99999
    message.from_user.language_code = "ru"
    message.answer = AsyncMock()

    session = AsyncMock()

    mock_chat = Chat(chat_id=-1001234567, title="FC Praha")
    mock_item = InventoryItem(
        id=1,
        chat_id=-1001234567,
        name="Мяч Select",
        category=InventoryCategory.BALLS,
        quantity=5,
        status=InventoryStatus.IN_STOCK,
        lifespan_days=365,
    )

    with patch("app.config.settings.admin_ids", [99999]):
        mock_chats_res = MagicMock()
        mock_chats_res.scalars.return_value.all.return_value = [mock_chat]

        mock_items_res = MagicMock()
        mock_items_res.scalars.return_value.all.return_value = [mock_item]

        session.execute.side_effect = [mock_chats_res, mock_items_res]

        await cmd_inventory(message, session)

        assert message.answer.called
        args, kwargs = message.answer.call_args
        text = args[0]
        assert "FC Praha" in text
        assert "Инвентарь" in text
        assert "В наличии" in text
        reply_markup = kwargs.get("reply_markup")
        assert reply_markup is not None
        assert len(reply_markup.inline_keyboard) > 0
        btn = reply_markup.inline_keyboard[0][0]
        assert "tab=inventory" in btn.web_app.url

@pytest.mark.asyncio
async def test_cmd_dashboard_has_inventory_button():
    message = MagicMock(spec=types.Message)
    message.chat = MagicMock(spec=types.Chat)
    message.chat.type = "private"
    message.from_user = MagicMock(spec=types.User)
    message.from_user.id = 99999
    message.from_user.language_code = "en"
    message.answer = AsyncMock()

    session = AsyncMock()

    with patch("app.config.settings.admin_ids", [99999]):
        await cmd_dashboard(message, session)

        assert message.answer.called
        _, kwargs = message.answer.call_args
        reply_markup = kwargs.get("reply_markup")
        assert reply_markup is not None
        assert len(reply_markup.inline_keyboard) == 2
        assert "tab=inventory" in reply_markup.inline_keyboard[1][0].web_app.url
