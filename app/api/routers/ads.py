import logging
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_session
from app.db.models import AdBanner
from app.api.auth import get_user_from_header

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/ads/random")
async def get_random_ad(
    chat_id: int = None, 
    user_id: int = Depends(get_user_from_header), 
    session: AsyncSession = Depends(get_session)
):
    """
    Returns a random active ad banner for the Mini-App.
    If chat_id is provided, it can fetch group-specific ads.
    Otherwise it fetches global ads (chat_id = None).
    """
    stmt = select(AdBanner).where(AdBanner.is_active == True)
    
    # Simple logic: get global ads AND chat-specific ads if chat_id is provided
    if chat_id:
        stmt = stmt.where((AdBanner.chat_id == None) | (AdBanner.chat_id == chat_id))
    else:
        stmt = stmt.where(AdBanner.chat_id == None)
        
    result = await session.execute(stmt)
    ads = result.scalars().all()
    
    if not ads:
        return {"status": "no_ads", "ad": None}
        
    # Weighted random choice based on show_probability
    weights = [ad.show_probability for ad in ads]
    chosen_ad = random.choices(ads, weights=weights, k=1)[0]
    
    return {
        "status": "ok",
        "ad": {
            "id": chosen_ad.id,
            "text": chosen_ad.text,
            "image_url": chosen_ad.image_url,
            "link": chosen_ad.link
        }
    }
