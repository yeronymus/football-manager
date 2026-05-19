import pytest
import time
import hmac
import hashlib
import urllib.parse
from fastapi import HTTPException
from app.api.auth import get_user_from_init_data, validate_init_data

# ===========================================================================
# 1. TESTS FOR get_user_from_init_data (JSON Decoding & Malformed Inputs)
# ===========================================================================

def test_get_user_from_init_data_malformed_json():
    init_data = urllib.parse.urlencode({"user": "{invalid}"})
    with pytest.raises(HTTPException) as exc_info:
        get_user_from_init_data(init_data)
    assert exc_info.value.status_code == 400


def test_get_user_from_init_data_success():
    init_data = urllib.parse.urlencode({"user": '{"id": 12345}'})
    user_id = get_user_from_init_data(init_data)
    assert user_id == 12345

def test_get_user_from_init_data_missing_id():
    init_data = urllib.parse.urlencode({"user": '{"name": "test"}'})
    with pytest.raises(HTTPException) as exc_info:
        get_user_from_init_data(init_data)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "User ID not found in initData"


# ===========================================================================
# 2. TESTS FOR validate_init_data (HMAC SHA-256 Signature Verification)
# ===========================================================================

def generate_valid_init_data(bot_token: str, auth_date: int = None, **kwargs) -> str:
    if auth_date is None:
        auth_date = int(time.time())

    data = {"auth_date": str(auth_date), **kwargs}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    data["hash"] = calculated_hash
    return urllib.parse.urlencode(data)

def test_validate_init_data_happy_path():
    bot_token = "test_bot_token"
    init_data = generate_valid_init_data(bot_token, user='{"id": 123}')
    assert validate_init_data(init_data, bot_token) is True

def test_validate_init_data_empty():
    assert validate_init_data("", "test_token") is False
    assert validate_init_data(None, "test_token") is False

def test_validate_init_data_no_hash():
    init_data = "auth_date=1234567890&user=abc"
    assert validate_init_data(init_data, "test_token") is False

def test_validate_init_data_invalid_hash():
    bot_token = "test_bot_token"
    init_data = generate_valid_init_data(bot_token, user='{"id": 123}')
    parsed = dict(urllib.parse.parse_qsl(init_data))
    parsed["hash"] = "invalid_hash_value"
    invalid_init_data = urllib.parse.urlencode(parsed)
    assert validate_init_data(invalid_init_data, bot_token) is False

def test_validate_init_data_expired_auth_date():
    bot_token = "test_bot_token"
    expired_time = int(time.time()) - 43201
    init_data = generate_valid_init_data(bot_token, auth_date=expired_time)
    assert validate_init_data(init_data, bot_token) is False

def test_validate_init_data_exception():
    assert validate_init_data(12345, "test_token") is False
