import hashlib
import hmac
import time
import urllib.parse
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
import pytest

from app.api.auth import validate_init_data, verify_tenant_membership
from app.core.services.audit import record_audit_log
from app.db.models import AuditLog


def _build_signed_init_data(bot_token: str, auth_date: int, user_id: int = 123456) -> str:
    params = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": f'{{"id":{user_id},"first_name":"Test"}}',
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    sig = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = sig
    return urllib.parse.urlencode(params)


def test_validate_init_data_hmac_and_replay_window():
    """Verifies HMAC-SHA256 signature validation, replay TTL, and future clock-skew rejection."""
    token = "0000000000:TEST_TOKEN_FOR_HMAC_VALIDATION_ONLY"
    now = int(time.time())

    valid_str = _build_signed_init_data(token, auth_date=now - 30)
    assert validate_init_data(valid_str, token, max_age_seconds=300) is True

    # Expired initData outside replay window
    expired_str = _build_signed_init_data(token, auth_date=now - 600)
    assert validate_init_data(expired_str, token, max_age_seconds=300) is False

    # Future clock-skew attack (> 60s in the future)
    future_str = _build_signed_init_data(token, auth_date=now + 300)
    assert validate_init_data(future_str, token, max_age_seconds=300) is False


@pytest.mark.asyncio
async def test_bola_tenant_membership_guard():
    """Verifies verify_tenant_membership blocks cross-tenant IDOR access with HTTP 403."""
    session = AsyncMock()

    # Case 1: Unaffiliated user (all 4 queries return None)
    empty_res = MagicMock()
    empty_res.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=empty_res)

    with pytest.raises(HTTPException) as exc:
        await verify_tenant_membership(chat_id=-100999, user_id=777777, session=session)
    assert exc.value.status_code == 403

    # Case 2: PlayerProfile member in tenant (3rd query returns user_id)
    member_res = MagicMock()
    member_res.scalar_one_or_none.return_value = 777777
    session.execute = AsyncMock(side_effect=[empty_res, empty_res, member_res])

    allowed = await verify_tenant_membership(chat_id=-100999, user_id=777777, session=session)
    assert allowed is True


def test_record_audit_log_stages_immutable_entry():
    """Verifies record_audit_log creates and stages an AuditLog model entry."""
    session = MagicMock()
    staged = []
    session.add = MagicMock(side_effect=lambda obj: staged.append(obj))

    entry = record_audit_log(
        session,
        action="TENANT_SETTINGS_UPDATE",
        actor_user_id=5001,
        chat_id=-100200,
        target_type="chat",
        target_id=-100200,
        payload={"billing_mode": "spayd_qr", "currency": "CZK"},
    )

    assert isinstance(entry, AuditLog)
    assert entry.action == "TENANT_SETTINGS_UPDATE"
    assert entry.actor_user_id == 5001
    assert entry.chat_id == -100200
    assert entry.target_id == "-100200"
    assert entry.payload["billing_mode"] == "spayd_qr"
    assert staged == [entry]
