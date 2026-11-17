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


@pytest.mark.asyncio
async def test_record_ad_click_and_mvp_reward_lifecycle():
    from app.api.routers.ads import (
        AdClickIn,
        RewardClaimIn,
        RewardStatusUpdateIn,
        record_ad_click,
        redeem_mvp_reward,
        submit_mvp_reward_loyalty_id,
    )
    from app.db.models import MvpRewardClaim

    session = AsyncMock()
    banner = AdBanner(
        id=10,
        text="21 Coffee MVP Partner",
        impressions_count=5,
        clicks_count=1,
        is_active=True,
    )
    session.get.return_value = banner

    click_res = await record_ad_click(
        banner_id=10,
        payload=AdClickIn(chat_id=-100, placement="game_top"),
        user_id=77,
        session=session,
    )
    assert click_res["clicks_count"] == 2
    assert click_res["impressions_count"] == 5

    claim = MvpRewardClaim(
        id=1,
        code="21C-G24-ABCD",
        chat_id=-100,
        game_id=24,
        user_id=77,
        sponsor_name="21 Coffee",
        reward_title="1x Free Coffee",
        status="ISSUED",
    )
    session.scalar.return_value = claim

    claim_res = await submit_mvp_reward_loyalty_id(
        code="21c-g24-abcd",
        payload=RewardClaimIn(loyalty_identifier="+420 777 123 456"),
        session=session,
    )
    assert claim_res["reward_status"] == "PENDING_CREDIT"
    assert claim.loyalty_identifier == "+420 777 123 456"

    redeem_res = await redeem_mvp_reward(
        code="21C-G24-ABCD",
        payload=RewardStatusUpdateIn(status="CREDITED"),
        session=session,
    )
    assert redeem_res["reward_status"] == "CREDITED"
    assert claim.status == "CREDITED"
