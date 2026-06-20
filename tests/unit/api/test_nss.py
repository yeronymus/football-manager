import pytest
from fastapi import HTTPException
from unittest.mock import patch, MagicMock
from app.api.routers.nss import get_cache_status

@pytest.mark.asyncio
@patch("app.api.routers.nss.cache_service")
async def test_get_cache_status_success(mock_cache_service):
    mock_cache_service.get_status.return_value = {"status": "connected", "keys": 10}
    res = await get_cache_status()
    assert res == {"status": "connected", "keys": 10}
    mock_cache_service.get_status.assert_called_once()

@pytest.mark.asyncio
@patch("app.api.routers.nss.cache_service")
async def test_get_cache_status_failure(mock_cache_service):
    mock_cache_service.get_status.side_effect = Exception("Redis error")
    with pytest.raises(HTTPException) as exc_info:
        await get_cache_status()
    assert exc_info.value.status_code == 500
    assert "Redis error" in exc_info.value.detail
