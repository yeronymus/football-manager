import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InventoryItem, InventoryStatus, InventoryCategory, Chat, ChatAdmin
from app.bot.i18n import t
from app.config import settings

logger = logging.getLogger(__name__)


def calculate_item_status(item: InventoryItem, now: Optional[datetime] = None) -> InventoryStatus:
    """
    Computes dynamic inventory status based on lifespan, purchase date, and stock quantity.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # If quantity is 0 or less, immediately marked as urgent purchase
    if item.quantity <= 0:
        return InventoryStatus.URGENT_PURCHASE

    if item.purchase_date and item.lifespan_days and item.lifespan_days > 0:
        # Normalize timezone
        p_date = item.purchase_date
        if p_date.tzinfo is None:
            p_date = p_date.replace(tzinfo=timezone.utc)
            
        elapsed_days = (now - p_date).days
        remaining_days = item.lifespan_days - elapsed_days

        if remaining_days <= 0:
            return InventoryStatus.URGENT_PURCHASE
        elif remaining_days <= 30 or remaining_days <= (item.lifespan_days * 0.2):
            return InventoryStatus.REPLACE_SOON
        else:
            return InventoryStatus.IN_STOCK

    # If manual override or no lifespan tracked, preserve existing or fallback
    return item.status or InventoryStatus.IN_STOCK


def get_item_metrics(item: InventoryItem, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Returns calculated telemetry metrics for UI display and status warnings.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    days_used = 0
    days_left: Optional[int] = None
    percent_used: float = 0.0

    if item.purchase_date:
        p_date = item.purchase_date
        if p_date.tzinfo is None:
            p_date = p_date.replace(tzinfo=timezone.utc)
        days_used = max(0, (now - p_date).days)

        if item.lifespan_days and item.lifespan_days > 0:
            days_left = item.lifespan_days - days_used
            percent_used = min(100.0, round((days_used / item.lifespan_days) * 100.0, 1))

    effective_status = calculate_item_status(item, now)

    return {
        "id": item.id,
        "chat_id": item.chat_id,
        "name": item.name,
        "category": item.category.value if hasattr(item.category, "value") else str(item.category),
        "quantity": item.quantity,
        "status": effective_status.value if hasattr(effective_status, "value") else str(effective_status),
        "purchase_date": item.purchase_date.isoformat() if item.purchase_date else None,
        "lifespan_days": item.lifespan_days,
        "days_used": days_used,
        "days_left": days_left,
        "percent_used": percent_used,
        "notes": item.notes,
        "alert_recipient_user_id": item.alert_recipient_user_id,
        "last_alert_sent_at": item.last_alert_sent_at.isoformat() if item.last_alert_sent_at else None,
    }


def mark_item_as_purchased(
    item: InventoryItem,
    quantity: Optional[int] = None,
    purchase_date: Optional[datetime] = None,
) -> InventoryItem:
    """
    Refreshes an inventory item after restocking/renewal.
    Resets purchase_date to today and status to IN_STOCK.
    """
    now = purchase_date or datetime.now(timezone.utc)
    item.purchase_date = now
    if quantity is not None and quantity > 0:
        item.quantity = quantity
    item.status = InventoryStatus.IN_STOCK
    return item


async def resolve_alert_recipient(
    session: AsyncSession,
    item: InventoryItem,
) -> Optional[int]:
    """
    Determines the Telegram user ID to receive inventory alerts:
    1. Item's explicit alert_recipient_user_id
    2. Primary admin of the chat
    3. Global system owner
    """
    if item.alert_recipient_user_id:
        return item.alert_recipient_user_id

    # Fallback to chat admin
    admin_stmt = (
        select(ChatAdmin.user_id)
        .where(ChatAdmin.chat_id == item.chat_id)
        .order_by(ChatAdmin.id.asc())
        .limit(1)
    )
    res = await session.execute(admin_stmt)
    first_admin = res.scalar_one_or_none()
    if first_admin:
        return first_admin

    return settings.system_owner_id


async def check_and_notify_inventory_alerts(
    bot: Any,
    session: AsyncSession,
    chat_id: Optional[int] = None,
    min_days_between_alerts: int = 7,
) -> List[Dict[str, Any]]:
    """
    Scans items, updates dynamic statuses, and delivers direct notifications for items needing attention.
    Rate-limited to prevent alert fatigue.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=min_days_between_alerts)

    stmt = select(InventoryItem)
    if chat_id:
        stmt = stmt.where(InventoryItem.chat_id == chat_id)

    res = await session.execute(stmt)
    items = res.scalars().all()

    alert_results = []

    for item in items:
        dynamic_status = calculate_item_status(item, now)
        if item.status != dynamic_status:
            item.status = dynamic_status

        # Only notify if status is warning or critical
        if dynamic_status not in (InventoryStatus.REPLACE_SOON, InventoryStatus.URGENT_PURCHASE):
            continue

        # Prevent duplicate spam
        if item.last_alert_sent_at and item.last_alert_sent_at > cutoff:
            continue

        recipient_uid = await resolve_alert_recipient(session, item)
        if not recipient_uid:
            continue

        # Fetch chat info for language and title
        chat = await session.get(Chat, item.chat_id)
        chat_lang = "en"
        chat_title = f"Chat {item.chat_id}"
        if chat:
            chat_lang = chat.language.value if hasattr(chat.language, "value") else str(chat.language or "en")
            chat_title = chat.title or chat_title

        metrics = get_item_metrics(item, now)
        is_urgent = (dynamic_status == InventoryStatus.URGENT_PURCHASE)
        key = "inventory_alert_urgent" if is_urgent else "inventory_alert_soon"

        category_label = t(f"inventory_cat_{item.category.value.lower()}", locale=chat_lang)
        msg_text = t(
            key,
            locale=chat_lang,
            item_name=item.name,
            group_title=chat_title,
            category=category_label,
            quantity=item.quantity,
            days_left=metrics["days_left"] if metrics["days_left"] is not None else 0,
            notes=item.notes or "-",
        )

        try:
            await bot.send_message(recipient_uid, msg_text, parse_mode="HTML")
            item.last_alert_sent_at = now
            alert_results.append({
                "item_id": item.id,
                "recipient": recipient_uid,
                "status": "delivered",
                "dynamic_status": dynamic_status.value,
            })
            logger.info(f"Delivered inventory alert for item {item.id} to user {recipient_uid}")
        except Exception as e:
            logger.warning(f"Failed to deliver inventory alert for item {item.id} to user {recipient_uid}: {e}")
            alert_results.append({
                "item_id": item.id,
                "recipient": recipient_uid,
                "status": "failed",
                "error": str(e),
            })

    await session.commit()
    return alert_results
