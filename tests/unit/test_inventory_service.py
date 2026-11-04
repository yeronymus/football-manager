import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.db.models import InventoryItem, InventoryCategory, InventoryStatus, Chat, ChatAdmin
from app.core.services.inventory import (
    calculate_item_status,
    get_item_metrics,
    mark_item_as_purchased,
    resolve_alert_recipient,
    check_and_notify_inventory_alerts,
)


def test_calculate_item_status_in_stock():
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    item = InventoryItem(
        chat_id=-1001,
        name="Match Ball",
        category=InventoryCategory.BALLS,
        quantity=5,
        purchase_date=now - timedelta(days=30),
        lifespan_days=365,
        status=InventoryStatus.IN_STOCK
    )
    status = calculate_item_status(item, now=now)
    assert status == InventoryStatus.IN_STOCK


def test_calculate_item_status_replace_soon():
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    # 180 days lifespan, bought 160 days ago -> 20 days left (<= 30 days)
    item = InventoryItem(
        chat_id=-1001,
        name="Orange Bibs",
        category=InventoryCategory.BIBS,
        quantity=10,
        purchase_date=now - timedelta(days=160),
        lifespan_days=180,
        status=InventoryStatus.IN_STOCK
    )
    status = calculate_item_status(item, now=now)
    assert status == InventoryStatus.REPLACE_SOON


def test_calculate_item_status_urgent_expired():
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    # 180 days lifespan, bought 200 days ago -> expired!
    item = InventoryItem(
        chat_id=-1001,
        name="Worn Bibs",
        category=InventoryCategory.BIBS,
        quantity=10,
        purchase_date=now - timedelta(days=200),
        lifespan_days=180,
        status=InventoryStatus.IN_STOCK
    )
    status = calculate_item_status(item, now=now)
    assert status == InventoryStatus.URGENT_PURCHASE


def test_calculate_item_status_zero_quantity():
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    item = InventoryItem(
        chat_id=-1001,
        name="Freeze Spray",
        category=InventoryCategory.MEDICAL,
        quantity=0,
        purchase_date=now,
        lifespan_days=90,
        status=InventoryStatus.IN_STOCK
    )
    status = calculate_item_status(item, now=now)
    assert status == InventoryStatus.URGENT_PURCHASE


def test_get_item_metrics():
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    item = InventoryItem(
        id=42,
        chat_id=-1001,
        name="Gloves",
        category=InventoryCategory.EQUIPMENT,
        quantity=2,
        purchase_date=now - timedelta(days=90),
        lifespan_days=180,
        notes="Stored in kit bag",
        alert_recipient_user_id=12345
    )
    metrics = get_item_metrics(item, now=now)
    assert metrics["id"] == 42
    assert metrics["days_used"] == 90
    assert metrics["days_left"] == 90
    assert metrics["percent_used"] == 50.0
    assert metrics["status"] == "IN_STOCK"
    assert metrics["alert_recipient_user_id"] == 12345


def test_mark_item_as_purchased():
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    item = InventoryItem(
        chat_id=-1001,
        name="Yellow Bibs",
        category=InventoryCategory.BIBS,
        quantity=2,
        purchase_date=now - timedelta(days=200),
        lifespan_days=180,
        status=InventoryStatus.URGENT_PURCHASE
    )
    mark_item_as_purchased(item, quantity=12, purchase_date=now)
    assert item.status == InventoryStatus.IN_STOCK
    assert item.quantity == 12
    assert item.purchase_date == now


@pytest.mark.asyncio
async def test_resolve_alert_recipient_custom_id():
    session = AsyncMock()
    item = InventoryItem(chat_id=-1001, name="Bibs", alert_recipient_user_id=88888)
    recipient = await resolve_alert_recipient(session, item)
    assert recipient == 88888


@pytest.mark.asyncio
async def test_check_and_notify_inventory_alerts_delivered():
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    bot = MagicMock()
    bot.send_message = AsyncMock()

    item = InventoryItem(
        id=1,
        chat_id=-1001,
        name="Orange Bibs",
        category=InventoryCategory.BIBS,
        quantity=10,
        purchase_date=now - timedelta(days=200),
        lifespan_days=180,
        status=InventoryStatus.IN_STOCK,
        alert_recipient_user_id=9990001,
        last_alert_sent_at=None
    )

    chat = Chat(chat_id=-1001, title="Test FC", language="ru")

    session = AsyncMock()
    # Mock items query
    items_mock = MagicMock()
    items_mock.scalars.return_value.all.return_value = [item]
    session.execute.return_value = items_mock
    session.get.return_value = chat

    results = await check_and_notify_inventory_alerts(bot, session, chat_id=-1001)

    assert len(results) == 1
    assert results[0]["status"] == "delivered"
    assert results[0]["recipient"] == 9990001
    assert bot.send_message.called
    assert item.last_alert_sent_at is not None


@pytest.mark.asyncio
async def test_resolve_alert_recipients_all_group_admins():
    from app.core.services.inventory import resolve_alert_recipients
    session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [111, 222, 333]
    session.execute.return_value = mock_res

    item = InventoryItem(chat_id=-1001, name="Bibs", alert_recipient_user_id=None)
    recipients = await resolve_alert_recipients(session, item)
    assert recipients == [111, 222, 333]


@pytest.mark.asyncio
async def test_send_item_alert_now_broadcasts_to_recipients():
    from app.core.services.inventory import send_item_alert_now
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    bot = MagicMock()
    bot.send_message = AsyncMock()

    item = InventoryItem(
        id=7,
        chat_id=-1001,
        name="Match Ball #5",
        category=InventoryCategory.BALLS,
        quantity=3,
        purchase_date=now - timedelta(days=400),
        lifespan_days=365,
        status=InventoryStatus.URGENT_PURCHASE,
        alert_recipient_user_id=None,
        last_alert_sent_at=None,
    )
    chat = Chat(chat_id=-1001, title="Prague Ballers", language="ru")

    session = AsyncMock()
    admin_mock = MagicMock()
    admin_mock.scalars.return_value.all.return_value = [555, 777]
    session.execute.return_value = admin_mock
    session.get.return_value = chat

    res = await send_item_alert_now(bot, session, item)
    assert len(res) == 2
    assert bot.send_message.call_count == 2
    assert item.last_alert_sent_at is not None
