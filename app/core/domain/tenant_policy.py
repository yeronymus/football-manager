import enum
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.domain.sport_presets import get_sport_preset


class BillingMode(str, enum.Enum):
    SPAYD_QR = "spayd_qr"
    MANUAL = "manual"
    FREE_CORPORATE = "free_corporate"
    CO_PAY_MULTISPORT = "co_pay_multisport"


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
    Eliminates magic timers, hardcoded rating deltas, and static organizer contacts (ADR-02, ADR-06),
    and stores pluggable event module overrides and corporate Co-Pay / MultiSport rules.
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

    # Phase 9-12: Pluggable Event Modules & Corporate Co-Pay / MultiSport / Retention
    enabled_modules: Optional[Dict[str, bool]] = None
    custom_roles: List[str] = Field(default_factory=list)
    employer_subsidy_pct: int = Field(default=0, ge=0, le=100)
    multisport_enabled: bool = False
    multisport_discount_amount: int = Field(default=150, ge=0, le=5000)
    data_retention_months: int = Field(default=24, ge=1, le=120)


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


def resolve_effective_modules(chat: Any = None) -> Dict[str, bool]:
    """
    Resolves the active event modules for a tenant by merging the selected
    preset's defaults (`sport_type`) with any per-group overrides in `policy.enabled_modules`.
    """
    sport_code = getattr(chat, "sport_type", None) if chat else "football"
    preset = get_sport_preset(sport_code)
    policy = resolve_tenant_policy(chat)
    return preset.resolve_modules(policy.enabled_modules)
