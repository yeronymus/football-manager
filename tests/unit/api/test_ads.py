import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.api.routers.ads import get_random_ad
from app.db.models import AdBanner

@pytest.mark.asyncio
async def test_get_random_ad_no_ads():
    session = AsyncMock()
    # Mock database to return empty list of ads
    mock_execute_res = MagicMock()
    mock_execute_res.scalars().all.return_value = []
    session.execute.return_value = mock_execute_res

    res = await get_random_ad(chat_id=123, user_id=456, session=session)
    assert res == {"status": "no_ads", "ad": None}

@pytest.mark.asyncio
@patch("random.choices")
async def test_get_random_ad_success(mock_choices):
    session = AsyncMock()
    ad1 = AdBanner(id=1, text="Test Ad 1", image_url="http://example.com/1.jpg", link="http://example.com/1", show_probability=1.0, is_active=True)
    ad2 = AdBanner(id=2, text="Test Ad 2", image_url="http://example.com/2.jpg", link="http://example.com/2", show_probability=2.0, is_active=True)
    
    mock_execute_res = MagicMock()
    mock_execute_res.scalars().all.return_value = [ad1, ad2]
    session.execute.return_value = mock_execute_res
    
    mock_choices.return_value = [ad2]

    res = await get_random_ad(chat_id=123, user_id=456, session=session)
    
    assert res["status"] == "ok"
    assert res["ad"]["id"] == 2
    assert res["ad"]["text"] == "Test Ad 2"
    mock_choices.assert_called_once_with([ad1, ad2], weights=[1.0, 2.0], k=1)
