import hashlib
import hmac
import urllib.parse
import json
import time
import logging
from fastapi import HTTPException, Header, Depends, Body, Path
from typing import Optional, Dict, Any
from pydantic import BaseModel
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
        
        if calculated_hash != hash_value:
            logger.warning(f"validate_init_data failed: Hash mismatch. Calc: {calculated_hash}, Recieved: {hash_value}")
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
    if settings.debug and not init_data:
        # Default debug user ID (replace with your admin ID for testing)
        return settings.admin_ids[0] if settings.admin_ids else 123456789
        
    parsed_data = dict(urllib.parse.parse_qsl(init_data))
    user_data = json.loads(parsed_data.get("user", "{}"))
    user_id = user_data.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in initData")
        
    return user_id

# Simple in-memory cache: (chat_id, user_id) -> (timestamp, is_admin)
admin_rights_cache = {}
CACHE_TTL = 300  # 5 minutes

async def check_admin_rights(chat_id: int, user_id: int):
    # System admins bypass all checks
    if user_id in settings.admin_ids or user_id == settings.system_owner_id:
        return True

    # 1. Check Cache
    current_time = time.time()
    cache_key = (chat_id, user_id)
    
    if cache_key in admin_rights_cache:
        timestamp, is_admin = admin_rights_cache[cache_key]
        if current_time - timestamp < CACHE_TTL:
            if not is_admin:
                raise HTTPException(status_code=403, detail="You must be an admin of the chat (Cached)")
            return True # Authorized

    # 2. Check Real (if not cached or expired)
    try:
        from app.bot.instance import bot
        user_member = await bot.get_chat_member(chat_id, user_id)
        is_admin = user_member.status in ["administrator", "creator"]
        
        # Update Cache
        admin_rights_cache[cache_key] = (current_time, is_admin)
        
        if not is_admin:
             raise HTTPException(status_code=403, detail="You must be an admin of the chat")
             
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

async def get_user_from_header(authorization: Optional[str] = Header(None)) -> int:
    """
    New Dependency: Extracts WebApp initData from the Authorization header.
    Format: 'Authorization: tma <initData>'
    """
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header. Use 'tma <initData>'")
    
    init_data = authorization.split(" ", 1)[1]
    if not validate_init_data(init_data, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData in header")
        
    return get_user_from_init_data(init_data)


