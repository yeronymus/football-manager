import base64
import datetime
import enum
import hashlib
import time
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Chat, Game, Organization


class PlanTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class OrgRole(str, enum.Enum):
    OWNER = "owner"
    BRANCH_ADMIN = "branch_admin"
    COORDINATOR = "coordinator"
    AUDITOR = "auditor"
    MEMBER = "member"


TIER_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    PlanTier.FREE.value: {
        "tier": "free",
        "name": "Free (Community)",
        "price_usd": 0,
        "max_chats": 1,
        "max_events_per_month": 4,
        "rate_limit_rps": 20,
        "features": {
            "spayd_qr": False,
            "ical_feed": False,
            "b2b_export": False,
            "co_pay_multisport": False,
            "byob_whitelabel": False,
            "org_analytics": False,
            "rls_isolation": True,
            "two_opt_optimizer": False,
        },
    },
    PlanTier.PRO.value: {
        "tier": "pro",
        "name": "Pro (Sports & Social Club)",
        "price_usd": 29,
        "max_chats": 5,
        "max_events_per_month": 9999,
        "rate_limit_rps": 100,
        "features": {
            "spayd_qr": True,
            "ical_feed": True,
            "b2b_export": False,
            "co_pay_multisport": False,
            "byob_whitelabel": False,
            "org_analytics": True,
            "rls_isolation": True,
            "two_opt_optimizer": True,
        },
    },
    PlanTier.ENTERPRISE.value: {
        "tier": "enterprise",
        "name": "Enterprise (Corporate B2B)",
        "price_usd": 199,
        "max_chats": 9999,
        "max_events_per_month": 9999,
        "rate_limit_rps": 500,
        "features": {
            "spayd_qr": True,
            "ical_feed": True,
            "b2b_export": True,
            "co_pay_multisport": True,
            "byob_whitelabel": True,
            "org_analytics": True,
            "rls_isolation": True,
            "two_opt_optimizer": True,
        },
    },
}


def resolve_plan_tier(raw: Any) -> PlanTier:
    if isinstance(raw, PlanTier):
        return raw
    val = str(raw or "free").strip().lower()
    for t in PlanTier:
        if t.value == val:
            return t
    return PlanTier.FREE


def get_org_capabilities(org_or_tier: Any = None) -> Dict[str, Any]:
    if isinstance(org_or_tier, Organization):
        tier = resolve_plan_tier(org_or_tier.plan_tier)
    else:
        tier = resolve_plan_tier(org_or_tier)
    return dict(TIER_CAPABILITIES[tier.value])


def check_feature_enabled(org_or_tier: Any, feature: str) -> bool:
    caps = get_org_capabilities(org_or_tier)
    return bool(caps.get("features", {}).get(feature, False))


async def assert_can_create_event(
    session: AsyncSession,
    chat_id: int,
    enforce_strict: bool = False,
) -> Dict[str, Any]:
    """
    Checks monthly event creation quota for the tenant's Organization plan tier.
    When `enforce_strict=True`, raises PermissionError if the monthly quota is exceeded.
    """
    chat = await session.get(Chat, chat_id)
    org = None
    if chat and getattr(chat, "organization_id", None):
        org = await session.get(Organization, chat.organization_id)

    tier = resolve_plan_tier(org.plan_tier if org else PlanTier.PRO)
    caps = get_org_capabilities(tier)
    max_events = caps["max_events_per_month"]

    now = datetime.datetime.now(datetime.timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    count_res = await session.execute(
        select(func.count(Game.id)).where(
            Game.chat_id == chat_id,
            Game.created_at >= month_start,
        )
    )
    used_this_month = int(count_res.scalar() or 0)
    allowed = used_this_month < max_events

    if enforce_strict and not allowed:
        raise PermissionError(
            f"Monthly event quota exceeded for plan '{tier.value}' ({used_this_month}/{max_events}). Upgrade to Pro or Enterprise."
        )

    return {
        "tier": tier.value,
        "used_this_month": used_this_month,
        "max_events_per_month": max_events,
        "allowed": allowed,
    }


def _derive_fernet_key(secret: Optional[str] = None) -> bytes:
    raw_secret = (secret or settings.bot_token or "default-enterprise-kms-secret").encode("utf-8")
    digest = hashlib.sha256(raw_secret).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret_envelope(plaintext: str, secret: Optional[str] = None) -> str:
    """Encrypts a sensitive credential (e.g. BYOB Telegram Bot Token or Vault snapshot) using Fernet AES-128-CBC + HMAC."""
    from cryptography.fernet import Fernet

    f = Fernet(_derive_fernet_key(secret))
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret_envelope(ciphertext: str, secret: Optional[str] = None) -> str:
    """Decrypts a Fernet envelope-encrypted credential."""
    from cryptography.fernet import Fernet

    f = Fernet(_derive_fernet_key(secret))
    return f.decrypt(ciphertext.encode("ascii")).decode("utf-8")


# In-memory / Redis hybrid Token Bucket for Noisy-Neighbor Protection
_TOKEN_BUCKETS: Dict[str, Dict[str, float]] = {}


def check_tenant_rate_limit(
    tenant_key: str,
    limit_rps: int = 50,
    now_ts: Optional[float] = None,
) -> bool:
    """
    Token Bucket algorithm per tenant (`organization_id` or `chat_id`) to prevent
    Noisy Neighbor exhaustion during peak tournament/event registration bursts.
    """
    now = now_ts if now_ts is not None else time.monotonic()
    capacity = float(max(1, limit_rps))
    bucket = _TOKEN_BUCKETS.get(tenant_key)

    if bucket is None:
        _TOKEN_BUCKETS[tenant_key] = {"tokens": capacity - 1.0, "last": now}
        return True

    elapsed = max(0.0, now - bucket["last"])
    replenished = min(capacity, bucket["tokens"] + elapsed * capacity)
    if replenished < 1.0:
        bucket["tokens"] = replenished
        bucket["last"] = now
        return False

    bucket["tokens"] = replenished - 1.0
    bucket["last"] = now
    return True


def reset_rate_limit_buckets() -> None:
    _TOKEN_BUCKETS.clear()
