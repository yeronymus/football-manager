from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routers.ads import AdClickIn, get_random_ad, record_ad_click
from app.core.services.sponsor_service import (
    get_sponsor_for_chat,
    notify_owner_of_mvp_reward,
    process_mvp_winners_sponsor_rewards,
)
from app.db.models import AdBanner, Chat, ChatMember, User


@pytest.mark.asyncio
@patch("app.api.routers.ads.get_sponsor_for_chat", return_value=None)
async def test_get_random_ad_no_ads(_mock_sponsor):
    session = AsyncMock()
    mock_execute_res = MagicMock()
    mock_execute_res.scalars().all.return_value = []
    session.execute.return_value = mock_execute_res

    res = await get_random_ad(chat_id=123, user_id=456, session=session)
    assert res == {"status": "no_ads", "ad": None}


@pytest.mark.asyncio
@patch("random.choices")
async def test_get_random_ad_success(mock_choices):
    session = AsyncMock()
    ad1 = AdBanner(
        id=1,
        text="Test Ad 1",
        image_url="http://example.com/1.jpg",
        link="http://example.com/1",
        show_probability=1,
        is_active=True,
    )
    ad2 = AdBanner(
        id=2,
        text="Test Ad 2",
        image_url="http://example.com/2.jpg",
        link="http://example.com/2",
        show_probability=2,
        is_active=True,
    )

    mock_execute_res = MagicMock()
    mock_execute_res.scalars().all.return_value = [ad1, ad2]
    session.execute.return_value = mock_execute_res

    mock_choices.return_value = [ad2]

    res = await get_random_ad(chat_id=-1003437568976, user_id=456, session=session, lang="en")

    assert res["status"] == "ok"
    assert res["ad"]["id"] == 2
    assert res["ad"]["sponsor_id"] == "21coffee"
    assert res["ad"]["link"] == "https://www.instagram.com/21coffeecz/"
    mock_choices.assert_called_once_with([ad1, ad2], weights=[1, 2], k=1)


@pytest.mark.asyncio
async def test_record_ad_click_increments_metrics():
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


@pytest.mark.asyncio
async def test_sponsor_service_bondus_onboarding_and_owner_english_notification():
    sponsor = get_sponsor_for_chat(-1003437568976)
    assert sponsor is not None
    assert sponsor.id == "21coffee"
    assert "bondus.cz" in sponsor.registration_url

    bot_mock = MagicMock()
    bot_mock.send_message = AsyncMock()

    # Case 1: Player has NO loyalty_card_id yet -> receives Bondus onboarding guide with DB name hinted
    user_new = User(user_id=11, full_name="Alisher Test", username="alish", language="ru")
    cm_new = ChatMember(
        chat_id=-1003437568976,
        user_id=11,
        full_name="Alisher Test",
        loyalty_card_id=None,
    )
    session = AsyncMock()
    session.get.return_value = user_new
    session.scalar.return_value = cm_new

    await process_mvp_winners_sponsor_rewards(
        bot=bot_mock,
        session=session,
        chat_id=-1003437568976,
        game_num=24,
        mvp_ids=[11],
    )
    bot_mock.send_message.assert_awaited_once()
    sent_kwargs = bot_mock.send_message.call_args.kwargs
    assert sent_kwargs["chat_id"] == 11
    assert "Alisher Test" in sent_kwargs["text"]
    assert "app.bondus.cz" in str(sent_kwargs["reply_markup"])

    # Case 2: Owner notification is strictly in English with 1 Free Coffee (no 100 CZK)
    bot_mock.send_message.reset_mock()
    session2 = AsyncMock()
    session2.get.side_effect = [
        Chat(chat_id=-1003437568976, title="Perfectland Ballers"),
        user_new,
    ]
    admin_res = MagicMock()
    admin_res.all.return_value = [(999001,)]
    session2.execute.return_value = admin_res

    sent = await notify_owner_of_mvp_reward(
        bot=bot_mock,
        session=session2,
        chat_id=-1003437568976,
        game_num=24,
        player_user_id=11,
        loyalty_name="Alisher Test",
        sponsor=sponsor,
    )
    assert sent == 1
    owner_text = bot_mock.send_message.call_args.kwargs["text"]
    assert "1 Free Coffee" in owner_text
    assert "100" not in owner_text
    assert "Alisher Test" in owner_text
