import enum
import re
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class BillingMode(str, enum.Enum):
    SPAYD_QR = "spayd_qr"
    MANUAL = "manual"
    FREE_CORPORATE = "free_corporate"


class RatingSystem(str, enum.Enum):
    SIMPLE_POINTS = "simple_points"
    DYNAMIC_ELO = "dynamic_elo"


class OrganizerContact(BaseModel):
    role: str = "Organizer"
    name: str = ""
    handle: str

    @field_validator("handle")
    @classmethod
    def normalize_handle(cls, v: str) -> str:
        return v.strip()

    @property
    def url(self) -> Optional[str]:
        h = self.handle.strip()
        if not h:
            return None
        if h.startswith(("https://", "http://", "mailto:")):
            return h
        if "@" in h and not h.startswith("@") and "." in h.split("@")[-1]:
            return f"mailto:{h}"
        clean_tg = h.lstrip("@")
        if re.fullmatch(r"[A-Za-z0-9_]{3,64}", clean_tg):
            return f"https://t.me/{clean_tg}"
        return None

    def resolved_url(self) -> Optional[str]:
        return self.url


class TenantPolicy(BaseModel):
    """
    3-tier parameterized policy configuration for a tenant (Telegram group / organization).
    Eliminates magic timers, hardcoded rating deltas, and static organizer contacts (ADR-02, ADR-06).
    """

    free_cancellation_hours: int = Field(default=24, ge=0, le=168)
    payment_reminder_hours_before: int = Field(default=12, ge=0, le=168)
    mvp_voting_delay_hours: float = Field(default=0.0, ge=0.0, le=72.0)
    mvp_voting_window_hours: int = Field(default=24, ge=1, le=168)
    yellow_card_default_weeks: int = Field(default=2, ge=1, le=52)
    red_card_default_weeks: int = Field(default=4, ge=1, le=52)
    rating_system: Literal["simple_points", "dynamic_elo"] = "simple_points"
    rating_win_points: int = Field(default=10, ge=-100, le=100)
    rating_draw_points: int = Field(default=0, ge=-100, le=100)
    rating_loss_points: int = Field(default=-5, ge=-100, le=100)
    rating_mvp_bonus: int = Field(default=5, ge=0, le=100)
    elo_k_base: int = Field(default=24, ge=4, le=100)
    elo_k_pro: int = Field(default=16, ge=4, le=100)
    elo_pro_games_threshold: int = Field(default=10, ge=1, le=200)
    organizer_contacts: List[OrganizerContact] = Field(default_factory=list)


def resolve_billing_mode(raw: Any) -> BillingMode:
    if isinstance(raw, BillingMode):
        return raw
    val = str(raw or "manual").strip().lower()
    for mode in BillingMode:
        if mode.value == val:
            return mode
    return BillingMode.MANUAL


def resolve_tenant_policy(chat_or_policy: Any = None) -> TenantPolicy:
    """Safely hydrates TenantPolicy from either a `Chat` model or raw JSON `dict`."""
    if chat_or_policy is None:
        return TenantPolicy()
    raw = (
        chat_or_policy
        if isinstance(chat_or_policy, dict)
        else getattr(chat_or_policy, "policy", None)
    )
    if not isinstance(raw, dict) or not raw:
        return TenantPolicy()
    try:
        return TenantPolicy.model_validate(raw)
    except Exception:
        valid_fields = {}
        defaults = TenantPolicy().model_dump()
        for key in defaults:
            if key in raw:
                valid_fields[key] = raw[key]
        try:
            return TenantPolicy.model_validate(valid_fields)
        except Exception:
            return TenantPolicy()
