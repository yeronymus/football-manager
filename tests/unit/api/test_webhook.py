import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from app.api.main import webhook
from app.config import settings

@pytest.mark.asyncio
async def test_webhook_missing_secret_token():
    request = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        await webhook(request=request, x_telegram_bot_api_secret_token=None)
    assert exc_info.value.status_code == 401
    assert "Unauthorized" in exc_info.value.detail

@pytest.mark.asyncio
async def test_webhook_invalid_secret_token():
    request = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        await webhook(request=request, x_telegram_bot_api_secret_token="wrong_secret_token")
    assert exc_info.value.status_code == 401
    assert "Unauthorized" in exc_info.value.detail

@pytest.mark.asyncio
@patch("app.api.main.dp.feed_update", new_callable=AsyncMock)
async def test_webhook_valid_secret_token(mock_feed_update):
    request = AsyncMock()
    request.json.return_value = {
        "update_id": 10001,
        "message": {
            "message_id": 1,
            "date": 1441645532,
            "chat": {"id": 111, "type": "private"},
            "from": {"id": 111, "is_bot": False, "first_name": "Test"},
            "text": "Hello"
        }
    }
    valid_token = settings.webhook_secret_token
    response = await webhook(request=request, x_telegram_bot_api_secret_token=valid_token)
    assert response == {"ok": True}
    mock_feed_update.assert_awaited_once()
