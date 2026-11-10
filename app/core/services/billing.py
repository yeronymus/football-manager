import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional

from app.config import settings
from app.core.domain.tenant_policy import BillingMode, resolve_billing_mode, resolve_tenant_policy

# Czech National Bank (ČNB) Modulo-11 weights from least-significant to most-significant digit
_CNB_WEIGHTS_6 = (10, 5, 8, 4, 2, 1)
_CNB_WEIGHTS_10 = (6, 3, 7, 9, 10, 5, 8, 4, 2, 1)

_CZ_DOMESTIC_RE = re.compile(r"^\s*(?:(\d{1,6})-)?(\d{2,10})/(\d{4})\s*$")
_IBAN_CLEAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")


def _check_cnb_mod11(digits_padded: str, weights: tuple[int, ...]) -> bool:
    total = sum(int(d) * w for d, w in zip(digits_padded, weights))
    return total % 11 == 0


def validate_iban_checksum(iban: str) -> bool:
    """Validates ISO 13616 / ISO 7064 Mod 97-10 checksum for any IBAN."""
    compact = re.sub(r"\s+", "", iban or "").upper()
    if not _IBAN_CLEAN_RE.fullmatch(compact):
        return False
    rearranged = compact[4:] + compact[:4]
    numeric = "".join(str(ord(ch) - 55) if ch.isalpha() else ch for ch in rearranged)
    return int(numeric) % 97 == 1


def czech_account_to_iban(account_str: str) -> Optional[str]:
    """
    Converts a Czech domestic account (`[prefix-]account/bank_code`, e.g. `19-2000145399/0800`)
    or an existing IBAN (`CZ...`, `SK...`, `DE...`) into a validated uppercase IBAN string.
    Returns None if `account_str` cannot be converted into a valid IBAN.
    """
    if not account_str:
        return None

    # Allow extra notes after account (e.g. "123456789/0800 (Note)") by extracting first token
    raw = account_str.strip()
    compact_iban_candidate = re.sub(r"\s+", "", raw).upper()
    if validate_iban_checksum(compact_iban_candidate):
        return compact_iban_candidate

    # Try matching domestic Czech account either whole string or leading token
    token = raw.split()[0] if raw.split() else raw
    match = _CZ_DOMESTIC_RE.match(raw) or _CZ_DOMESTIC_RE.match(token)
    if not match:
        return None

    prefix_raw, number_raw, bank_code = match.groups()
    prefix = (prefix_raw or "").zfill(6)
    number = number_raw.zfill(10)

    if int(number) == 0:
        return None
    if not _check_cnb_mod11(prefix, _CNB_WEIGHTS_6):
        return None
    if not _check_cnb_mod11(number, _CNB_WEIGHTS_10):
        return None

    bban = f"{bank_code}{prefix}{number}"
    # Compute check digits: move "CZ00" -> "123500" to end
    numeric_for_mod = f"{bban}123500"
    check_digits = 98 - (int(numeric_for_mod) % 97)
    return f"CZ{check_digits:02d}{bban}"


def sanitize_spayd_message(message: str, max_len: int = 60) -> str:
    """Strips diacritics and SPAYD delimiter characters (`*`) per Czech Banking Standard."""
    normalized = unicodedata.normalize("NFKD", message or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9 _.,#/-]", "", ascii_text).strip()
    return cleaned[:max_len]


def build_spayd_payload(
    iban_or_account: str,
    amount: float | int,
    currency: str = "CZK",
    variable_symbol: Optional[str | int] = None,
    message: Optional[str] = None,
) -> Optional[str]:
    """
    Builds a Czech QR Platba SPAYD 1.0 payload (`SPD*1.0*ACC:...*AM:...*CC:...`).
    Returns None if `iban_or_account` is not a valid IBAN or Czech bank account, or `amount <= 0`.
    """
    if amount is None or float(amount) <= 0:
        return None

    iban = czech_account_to_iban(iban_or_account)
    if not iban:
        return None

    cc = (currency or settings.default_currency or "CZK").upper().strip()[:3]
    parts = [
        "SPD*1.0",
        f"ACC:{iban}",
        f"AM:{float(amount):.2f}",
        f"CC:{cc}",
    ]

    if variable_symbol is not None:
        vs_digits = re.sub(r"\D", "", str(variable_symbol))[:10]
        if vs_digits:
            parts.append(f"X-VS:{vs_digits}")

    if message:
        clean_msg = sanitize_spayd_message(message)
        if clean_msg:
            parts.append(f"MSG:{clean_msg}")

    return "*".join(parts)


@dataclass
class HybridSettlementBreakdown:
    """
    Financial clearing breakdown for Corporate Co-Pay & MultiSport / Benefit Plus events.
    """

    total_event_cost: int
    participant_count: int
    multisport_count: int
    employer_subsidy_pct: int
    employer_share: int
    multisport_total_discount: int
    net_participant_pool: int
    per_paying_participant_amount: int
    per_multisport_participant_amount: int


def calculate_hybrid_settlement(
    total_cost: int,
    participant_count: int,
    multisport_count: int = 0,
    employer_subsidy_pct: int = 0,
    multisport_discount: int = 150,
) -> HybridSettlementBreakdown:
    """
    Calculates split-billing across employer subsidy (% Co-Pay) and MultiSport card deductions.
    """
    total = max(0, int(total_cost or 0))
    n_total = max(1, int(participant_count or 1))
    n_ms = max(0, min(int(multisport_count or 0), n_total))
    sub_pct = max(0, min(int(employer_subsidy_pct or 0), 100))
    ms_disc = max(0, int(multisport_discount or 0))

    employer_share = int(round(total * (sub_pct / 100.0)))
    after_employer = max(0, total - employer_share)
    ms_total_discount = min(after_employer, n_ms * ms_disc)
    net_pool = max(0, after_employer - ms_total_discount)

    n_paying = max(0, n_total - n_ms)
    if n_paying > 0:
        per_paying = int(round(net_pool / n_paying))
        per_ms = 0
    else:
        per_paying = 0
        per_ms = int(round(net_pool / n_total))

    return HybridSettlementBreakdown(
        total_event_cost=total,
        participant_count=n_total,
        multisport_count=n_ms,
        employer_subsidy_pct=sub_pct,
        employer_share=employer_share,
        multisport_total_discount=ms_total_discount,
        net_participant_pool=net_pool,
        per_paying_participant_amount=per_paying,
        per_multisport_participant_amount=per_ms,
    )


@dataclass
class GameBillingSummary:
    billing_mode: str
    currency: str
    amount: int
    is_free: bool
    payment_info: Optional[str]
    iban: Optional[str]
    variable_symbol: Optional[str]
    spayd_payload: Optional[str]


def resolve_game_billing(
    game: Any,
    chat: Any = None,
    game_number: Optional[int] = None,
) -> GameBillingSummary:
    """Computes effective billing metadata for a match across all enterprise modes."""
    mode = resolve_billing_mode(getattr(chat, "billing_mode", None) if chat else None)
    currency = (
        (getattr(chat, "currency", None) if chat else None)
        or settings.default_currency
        or "CZK"
    ).upper()

    if mode == BillingMode.FREE_CORPORATE:
        return GameBillingSummary(
            billing_mode=mode.value,
            currency=currency,
            amount=0,
            is_free=True,
            payment_info=None,
            iban=None,
            variable_symbol=None,
            spayd_payload=None,
        )

    amount = int(getattr(game, "price", 0) or 0)
    policy = resolve_tenant_policy(chat) if chat else None
    if policy and policy.employer_subsidy_pct > 0 and amount > 0:
        amount = max(0, int(round(amount * (100 - policy.employer_subsidy_pct) / 100.0)))

    raw_payment = getattr(game, "payment_info", None) or (
        getattr(chat, "payment_info", None) if chat else None
    )

    if amount <= 0:
        return GameBillingSummary(
            billing_mode=mode.value,
            currency=currency,
            amount=0,
            is_free=True,
            payment_info=raw_payment,
            iban=None,
            variable_symbol=None,
            spayd_payload=None,
        )

    iban = czech_account_to_iban(raw_payment) if raw_payment else None
    num = game_number or getattr(game, "id", None)
    vs = str(getattr(game, "id", "")) if getattr(game, "id", None) else None
    spayd = None

    if mode in (BillingMode.SPAYD_QR, BillingMode.CO_PAY_MULTISPORT) and iban:
        loc = getattr(game, "location", "") or "Event"
        msg = f"Match #{num} {loc}".strip() if num else f"Match {loc}".strip()
        spayd = build_spayd_payload(
            iban_or_account=iban,
            amount=amount,
            currency=currency,
            variable_symbol=vs,
            message=msg,
        )

    return GameBillingSummary(
        billing_mode=mode.value,
        currency=currency,
        amount=amount,
        is_free=False,
        payment_info=raw_payment,
        iban=iban,
        variable_symbol=vs,
        spayd_payload=spayd,
    )
