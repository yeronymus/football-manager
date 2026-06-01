import hashlib
import hmac
import urllib.parse
import json
import time
import logging
from fastapi import HTTPException, Header, Depends, Body
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings

logger = logging.getLogger(__name__)

def validate_init_data(init_data: str, bot_token: str) -> bool:
    """
    Validates Telegram WebApp initData.
    """
    try:
        if not init_data:
            logger.warning("validate_init_data failed: Empty init_data")
            return False
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in parsed_data:
            logger.warning("validate_init_data failed: No hash in init_data")
            return False
        
        hash_value = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        # 🛡️ Sentinel: Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(calculated_hash, hash_value):
            logger.warning("validate_init_data failed: Hash mismatch.")
            return False
            
        # Check auth_date for replay attacks (Increased to 12h for ease of use)
        auth_date = int(parsed_data.get("auth_date", 0))
        if time.time() - auth_date > 43200:
            logger.warning("validate_init_data failed: Auth date expired")
            return False
            
        return True
    except Exception as e:
        logger.error(f"validate_init_data exception: {e}")
        return False

def get_user_from_init_data(init_data: str) -> int:
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")
        
    parsed_data = dict(urllib.parse.parse_qsl(init_data))

    try:
        user_data = json.loads(parsed_data.get("user", "{}"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid user JSON in initData")

    user_id = user_data.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in initData")
        
    return user_id

async def check_admin_rights(chat_id: int, user_id: int, session: Optional[AsyncSession] = None):
    # System admins from config bypass checks (fallback/bootstrap)
    if user_id in settings.admin_ids or user_id == settings.system_owner_id:
        return True

    try:
        from app.db.models import User, ChatAdmin
        from sqlalchemy import select
        
        # Internal helper to perform the check
        async def _perform_check(s: AsyncSession):
            # 1. Check if user is superadmin in DB
            user_res = await s.execute(select(User).where(User.user_id == user_id))
            user = user_res.scalar_one_or_none()
            
            if user and getattr(user, 'is_superadmin', False):
                return True
                
            # 2. Check if user is admin of this specific chat
            admin_res = await s.execute(
                select(ChatAdmin).where(
                    ChatAdmin.chat_id == chat_id, 
                    ChatAdmin.user_id == user_id
                )
            )
            chat_admin = admin_res.scalar_one_or_none()
            
            if not chat_admin:
                raise HTTPException(status_code=403, detail="You must be an admin of this group")
            return True

        if session:
            return await _perform_check(session)
        else:
            from app.db.database import async_session_maker
            async with async_session_maker() as new_session:
                return await _perform_check(new_session)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot verify user rights: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot verify user rights: {str(e)}")

# --- Dependencies for FastAPI ---

async def get_current_user_id(initData: str = Body(..., embed=False, alias="initData")) -> int:
    """Legacy Dependency: Extract user_id from body."""
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    return get_user_from_init_data(initData)

async def require_chat_admin(
    chat_id: int = Body(...),
    user_id: int = Depends(get_current_user_id)
) -> int:
    """Legacy Dependency: ensure user_id is admin of the chat_id from body."""
    await check_admin_rights(chat_id, user_id)
    return user_id

async def get_user_from_header(
    authorization: Optional[str] = Header(None),
    initData: Optional[str] = None # Fallback for cached WebApps
) -> int:
    """
    Extracts WebApp initData from the Authorization header or query params.
    Format: 'Authorization: tma <initData>' or '?initData=<initData>'
    """
    init_data = None
    
    # 1. Try Header
    if authorization and authorization.startswith("tma "):
        init_data = authorization.split(" ", 1)[1]
    
    # 2. Try Query Param (Fallback for aggressive Telegram caching)
    if not init_data and initData:
        init_data = initData
        
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing Authorization header or initData query param")
    
    if not validate_init_data(init_data, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
        
    return get_user_from_init_data(init_data)


