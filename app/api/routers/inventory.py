import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user_from_header, check_admin_rights
from app.db.database import get_session
from app.config import settings
from app.db.models import InventoryItem, InventoryCategory, InventoryStatus, Chat, ChatAdmin, User
from app.core.services.inventory import (
    calculate_item_status,
    get_item_metrics,
    mark_item_as_purchased,
    check_and_notify_inventory_alerts,
    send_item_alert_now,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/groups/{chat_id}/inventory", tags=["inventory"])


class InventoryItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: InventoryCategory = InventoryCategory.OTHER
    quantity: int = Field(1, ge=0)
    purchase_date: Optional[datetime] = None
    lifespan_days: Optional[int] = Field(None, ge=1)
    notes: Optional[str] = None
    alert_recipient_user_id: Optional[int] = None


class InventoryItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    category: Optional[InventoryCategory] = None
    quantity: Optional[int] = Field(None, ge=0)
    status: Optional[InventoryStatus] = None
    purchase_date: Optional[datetime] = None
    lifespan_days: Optional[int] = Field(None, ge=1)
    notes: Optional[str] = None
    alert_recipient_user_id: Optional[int] = None


class InventoryItemOut(BaseModel):
    id: int
    chat_id: int
    name: str
    category: str
    quantity: int
    status: str
    purchase_date: Optional[str] = None
    lifespan_days: Optional[int] = None
    days_used: int = 0
    days_left: Optional[int] = None
    percent_used: float = 0.0
    notes: Optional[str] = None
    alert_recipient_user_id: Optional[int] = None
    last_alert_sent_at: Optional[str] = None


class InventoryAdminRecipientOut(BaseModel):
    user_id: int
    full_name: str
    username: Optional[str] = None


class InventoryListOut(BaseModel):
    chat_id: int
    total_count: int
    urgent_count: int
    warning_count: int
    items: List[InventoryItemOut]


@router.get("", response_model=InventoryListOut)
async def get_chat_inventory(
    chat_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Retrieves all inventory items for a group with calculated wear and alert statuses.
    """
    await check_admin_rights(chat_id, user_id, session=session)

    stmt = select(InventoryItem).where(InventoryItem.chat_id == chat_id).order_by(InventoryItem.category, InventoryItem.id)
    res = await session.execute(stmt)
    raw_items = res.scalars().all()

    now = datetime.now(timezone.utc)
    items_out = []
    urgent_count = 0
    warning_count = 0

    for item in raw_items:
        metrics = get_item_metrics(item, now)
        items_out.append(InventoryItemOut(**metrics))

        if metrics["status"] == InventoryStatus.URGENT_PURCHASE.value:
            urgent_count += 1
        elif metrics["status"] == InventoryStatus.REPLACE_SOON.value:
            warning_count += 1

    return InventoryListOut(
        chat_id=chat_id,
        total_count=len(items_out),
        urgent_count=urgent_count,
        warning_count=warning_count,
        items=items_out,
    )


@router.post("", response_model=InventoryItemOut)
async def create_inventory_item(
    chat_id: int,
    payload: InventoryItemCreate,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Creates a new inventory item for the group.
    """
    await check_admin_rights(chat_id, user_id, session=session)

    item = InventoryItem(
        chat_id=chat_id,
        name=payload.name.strip(),
        category=payload.category,
        quantity=payload.quantity,
        purchase_date=payload.purchase_date or datetime.now(timezone.utc),
        lifespan_days=payload.lifespan_days,
        notes=payload.notes.strip() if payload.notes else None,
        alert_recipient_user_id=payload.alert_recipient_user_id or user_id,
    )
    item.status = calculate_item_status(item)

    session.add(item)
    await session.commit()
    await session.refresh(item)

    metrics = get_item_metrics(item)
    return InventoryItemOut(**metrics)


@router.put("/{item_id}", response_model=InventoryItemOut)
async def update_inventory_item(
    chat_id: int,
    item_id: int,
    payload: InventoryItemUpdate,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Updates properties of an existing inventory item.
    """
    await check_admin_rights(chat_id, user_id, session=session)

    item = await session.get(InventoryItem, item_id)
    if not item or item.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.category is not None:
        item.category = payload.category
    if payload.quantity is not None:
        item.quantity = payload.quantity
    if payload.status is not None:
        item.status = payload.status
    if payload.purchase_date is not None:
        item.purchase_date = payload.purchase_date
    if payload.lifespan_days is not None:
        item.lifespan_days = payload.lifespan_days
    if payload.notes is not None:
        item.notes = payload.notes.strip() if payload.notes else None
    if payload.alert_recipient_user_id is not None:
        item.alert_recipient_user_id = payload.alert_recipient_user_id

    # Recalculate dynamic status unless explicitly set
    if payload.status is None:
        item.status = calculate_item_status(item)

    await session.commit()
    await session.refresh(item)

    metrics = get_item_metrics(item)
    return InventoryItemOut(**metrics)


@router.post("/{item_id}/purchased", response_model=InventoryItemOut)
async def mark_inventory_purchased(
    chat_id: int,
    item_id: int,
    quantity: Optional[int] = Query(None, ge=1),
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Refreshes the item after renewal/purchase (resets purchase_date to now and status to IN_STOCK).
    """
    await check_admin_rights(chat_id, user_id, session=session)

    item = await session.get(InventoryItem, item_id)
    if not item or item.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    mark_item_as_purchased(item, quantity=quantity)
    await session.commit()
    await session.refresh(item)

    metrics = get_item_metrics(item)
    return InventoryItemOut(**metrics)


@router.delete("/{item_id}")
async def delete_inventory_item(
    chat_id: int,
    item_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Deletes an inventory item.
    """
    await check_admin_rights(chat_id, user_id, session=session)

    item = await session.get(InventoryItem, item_id)
    if not item or item.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    await session.delete(item)
    await session.commit()
    return {"status": "ok", "deleted_item_id": item_id}


@router.post("/trigger_alerts")
async def trigger_inventory_alerts(
    chat_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Explicitly checks inventory conditions and delivers any pending alert notifications to administrators.
    """
    await check_admin_rights(chat_id, user_id, session=session)

    from app.bot.instance import bot

    results = await check_and_notify_inventory_alerts(
        bot=bot,
        session=session,
        chat_id=chat_id,
        min_days_between_alerts=0,  # Manual trigger bypasses cooldown
    )
    return {"status": "ok", "alerts_sent": len(results), "details": results}


@router.get("/admins", response_model=List[InventoryAdminRecipientOut])
async def get_inventory_admins(
    chat_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Returns list of administrators for this group chat who can be assigned as alert recipients.
    """
    await check_admin_rights(chat_id, user_id, session=session)

    stmt = (
        select(User)
        .join(ChatAdmin, ChatAdmin.user_id == User.user_id)
        .where(ChatAdmin.chat_id == chat_id)
        .distinct()
    )
    res = await session.execute(stmt)
    users = list(res.scalars().all())
    existing_uids = {u.user_id for u in users}

    extra_uids = []
    if user_id not in existing_uids:
        extra_uids.append(user_id)
    if settings.system_owner_id and settings.system_owner_id not in existing_uids and settings.system_owner_id not in extra_uids:
        extra_uids.append(settings.system_owner_id)

    if extra_uids:
        extra_stmt = select(User).where(User.user_id.in_(extra_uids))
        extra_res = await session.execute(extra_stmt)
        users.extend(extra_res.scalars().all())

    out = []
    seen = set()
    for u in users:
        if u.user_id in seen:
            continue
        seen.add(u.user_id)
        out.append(
            InventoryAdminRecipientOut(
                user_id=u.user_id,
                full_name=u.full_name or f"User {u.user_id}",
                username=u.username,
            )
        )
    return out


@router.post("/{item_id}/send_alert")
async def send_single_inventory_alert(
    chat_id: int,
    item_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Immediately sends an alert notification for this specific inventory item to its assigned recipient(s).
    """
    await check_admin_rights(chat_id, user_id, session=session)

    item = await session.get(InventoryItem, item_id)
    if not item or item.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    from app.bot.instance import bot

    results = await send_item_alert_now(bot=bot, session=session, item=item)
    return {"status": "ok", "delivered_to": len(results), "details": results}
