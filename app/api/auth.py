import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Optional
from fastapi import Body, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.database import get_session

logger = logging.getLogger(__name__)


def _is_dev_bypass_enabled() -> bool:
    return settings.app_env == "local_dev" and settings.dev_auth_bypass


INIT_DATA_MAX_AGE_SECONDS = 43200


def validate_init_data(
    init_data: str, bot_token: str, max_age_seconds: int = INIT_DATA_MAX_AGE_SECONDS
) -> bool:
    """
    Validates Telegram WebApp initData using constant-time HMAC-SHA256 verification
    and enforces both replay-window expiration and future clock-skew bounds.
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
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, hash_value):
            logger.warning("validate_init_data failed: Hash mismatch.")
            return False

        auth_date = int(parsed_data.get("auth_date", 0))
        now = time.time()
        if now - auth_date > max_age_seconds or (auth_date - now) > 60:
            logger.warning("validate_init_data failed: Auth date expired or invalid clock skew")
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


async def check_admin_rights(
    chat_id: int, user_id: int, session: Optional[AsyncSession] = None
):
    if user_id in settings.admin_ids or user_id == settings.system_owner_id:
        return True

    try:
        from sqlalchemy import select
        from app.db.models import ChatAdmin, User

        async def _perform_check(s: AsyncSession):
            user_res = await s.execute(select(User).where(User.user_id == user_id))
            user = user_res.scalar_one_or_none()

            if user and getattr(user, "is_superadmin", False):
                return True

            admin_res = await s.execute(
                select(ChatAdmin).where(
                    ChatAdmin.chat_id == chat_id,
                    ChatAdmin.user_id == user_id,
                )
            )
            chat_admin = admin_res.scalar_one_or_none()

            if not chat_admin:
                raise HTTPException(
                    status_code=403, detail="You must be an admin of this group"
                )
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
        raise HTTPException(
            status_code=400, detail=f"Cannot verify user rights: {str(e)}"
        )


async def get_current_user_id(
    initData: Optional[str] = Body(None, embed=False, alias="initData"),
) -> int:
    """Extract user_id from body initData (supports local_dev bypass when enabled)."""
    if (not initData or initData == "dev_bypass") and _is_dev_bypass_enabled():
        return settings.dev_user_id
    if not initData:
        raise HTTPException(status_code=401, detail="Missing initData")
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    return get_user_from_init_data(initData)


async def require_chat_admin(
    chat_id: int = Body(...),
    user_id: int = Depends(get_current_user_id),
) -> int:
    """Ensure user_id is admin of the chat_id from body."""
    await check_admin_rights(chat_id, user_id)
    return user_id


async def get_user_from_header(
    authorization: Optional[str] = Header(None),
    initData: Optional[str] = None,
) -> int:
    """
    Extracts WebApp initData from Authorization header or query fallback.
    Supports explicit 'Authorization: dev <user_id>' or automatic fallback strictly in local_dev.
    """
    if _is_dev_bypass_enabled() and authorization and authorization.startswith("dev "):
        try:
            return int(authorization.split(" ", 1)[1].strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dev user ID")

    init_data = None
    if authorization and authorization.startswith("tma "):
        init_data = authorization.split(" ", 1)[1]

    if not init_data and initData:
        init_data = initData

    if (not init_data or init_data == "dev_bypass") and _is_dev_bypass_enabled():
        return settings.dev_user_id

    if not init_data:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header or initData query param",
        )

    if not validate_init_data(init_data, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")

    return get_user_from_init_data(init_data)


async def require_system_owner(
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
) -> int:
    """Restricts operational/diagnostic endpoints strictly to System Owners / Superadmins."""
    if user_id == settings.system_owner_id or user_id in settings.admin_ids:
        return user_id

    from sqlalchemy import select
    from app.db.models import User

    res = await session.execute(select(User).where(User.user_id == user_id))
    user = res.scalar_one_or_none()
    if user and getattr(user, "is_superadmin", False):
        return user_id

    raise HTTPException(status_code=403, detail="System owner privileges required")


async def build_admin_games_query(user_id: int, session: AsyncSession):
    """
    Builds a SQLAlchemy query for Games that the user is allowed to manage.
    """
    from sqlalchemy import select
    from app.db.models import ChatAdmin, Game, User

    if user_id in settings.admin_ids or user_id == settings.system_owner_id:
        return select(Game)

    user_res = await session.execute(select(User).where(User.user_id == user_id))
    user = user_res.scalar_one_or_none()

    if user and getattr(user, "is_superadmin", False):
        return select(Game)

    return (
        select(Game)
        .join(ChatAdmin, Game.chat_id == ChatAdmin.chat_id)
        .where(ChatAdmin.user_id == user_id)
    )


async def verify_tenant_membership(
    chat_id: int, user_id: int, session: AsyncSession
) -> bool:
    """
    BOLA/IDOR Tenant Guard (ADR-09):
    Verifies that `user_id` is affiliated with tenant `chat_id` (as a ChatAdmin,
    PlayerProfile member, historical match participant, or system owner/superadmin).
    Raises HTTP 403 if the caller has no relationship with the requested tenant.
    """
    if user_id in settings.admin_ids or user_id == settings.system_owner_id:
        return True

    from sqlalchemy import select
    from app.db.models import ChatAdmin, Game, PlayerProfile, Signup, User

    user_res = await session.execute(select(User).where(User.user_id == user_id))
    user = user_res.scalar_one_or_none()
    if user and getattr(user, "is_superadmin", False):
        return True

    admin_res = await session.execute(
        select(ChatAdmin.user_id).where(
            ChatAdmin.chat_id == chat_id, ChatAdmin.user_id == user_id
        )
    )
    if admin_res.scalar_one_or_none() is not None:
        return True

    prof_res = await session.execute(
        select(PlayerProfile.user_id).where(
            PlayerProfile.chat_id == chat_id, PlayerProfile.user_id == user_id
        )
    )
    if prof_res.scalar_one_or_none() is not None:
        return True

    signup_res = await session.execute(
        select(Signup.id)
        .join(Game, Game.id == Signup.game_id)
        .where(Game.chat_id == chat_id, Signup.user_id == user_id)
        .limit(1)
    )
    if signup_res.scalar_one_or_none() is not None:
        return True

    raise HTTPException(
        status_code=403,
        detail="Access denied: user is not a member of this tenant organization",
    )

