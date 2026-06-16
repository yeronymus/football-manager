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

def test_get_user_from_init_data_empty_input():
    with pytest.raises(HTTPException) as exc_info:
        get_user_from_init_data("")
    assert exc_info.value.status_code == 401
    assert "Missing initData" in exc_info.value.detail

def test_get_user_from_init_data_none_input():
    with pytest.raises(HTTPException) as exc_info:
        get_user_from_init_data(None)
    assert exc_info.value.status_code == 401


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


# ===========================================================================
# 3. TESTS FOR check_admin_rights
# ===========================================================================

from unittest.mock import AsyncMock, MagicMock, patch
from app.api.auth import check_admin_rights
from app.config import settings

@pytest.mark.asyncio
async def test_check_admin_rights_bypass():
    with patch.object(settings, "admin_ids", [9999]), \
         patch.object(settings, "system_owner_id", 8888):
        
        # Bypass by admin ID
        res = await check_admin_rights(chat_id=111, user_id=9999)
        assert res is True
        
        # Bypass by system owner ID
        res2 = await check_admin_rights(chat_id=111, user_id=8888)
        assert res2 is True

@pytest.mark.asyncio
async def test_check_admin_rights_superadmin_db():
    session = AsyncMock()
    
    # Mock user query to return user with is_superadmin=True
    mock_user = MagicMock()
    mock_user.is_superadmin = True
    
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = mock_user
    
    session.execute.return_value = mock_execute_res
    
    # We bypass config admin ids
    with patch.object(settings, "admin_ids", []), \
         patch.object(settings, "system_owner_id", None):
        
        res = await check_admin_rights(chat_id=111, user_id=123, session=session)
        assert res is True
        assert session.execute.call_count == 1

@pytest.mark.asyncio
async def test_check_admin_rights_chat_admin_db():
    session = AsyncMock()
    
    # 1st execute (User check) -> returns user with is_superadmin=False
    mock_user = MagicMock()
    mock_user.is_superadmin = False
    
    # 2nd execute (ChatAdmin check) -> returns a ChatAdmin object
    mock_chat_admin = MagicMock()
    
    # We can setup a side_effect for session.execute
    mock_res_user = MagicMock()
    mock_res_user.scalar_one_or_none.return_value = mock_user
    
    mock_res_chat_admin = MagicMock()
    mock_res_chat_admin.scalar_one_or_none.return_value = mock_chat_admin
    
    session.execute.side_effect = [mock_res_user, mock_res_chat_admin]
    
    with patch.object(settings, "admin_ids", []), \
         patch.object(settings, "system_owner_id", None):
         
        res = await check_admin_rights(chat_id=111, user_id=123, session=session)
        assert res is True
        assert session.execute.call_count == 2

@pytest.mark.asyncio
async def test_check_admin_rights_forbidden():
    session = AsyncMock()
    
    # 1st execute (User check) -> returns None
    # 2nd execute (ChatAdmin check) -> returns None
    mock_res_none = MagicMock()
    mock_res_none.scalar_one_or_none.return_value = None
    
    session.execute.return_value = mock_res_none
    
    with patch.object(settings, "admin_ids", []), \
         patch.object(settings, "system_owner_id", None):
         
        with pytest.raises(HTTPException) as exc_info:
            await check_admin_rights(chat_id=111, user_id=123, session=session)
        
        assert exc_info.value.status_code == 403
        assert "You must be an admin of this group" in exc_info.value.detail

@pytest.mark.asyncio
async def test_check_admin_rights_db_error():
    session = AsyncMock()
    session.execute.side_effect = Exception("DB Disconnect")
    
    with patch.object(settings, "admin_ids", []), \
         patch.object(settings, "system_owner_id", None):
         
        with pytest.raises(HTTPException) as exc_info:
            await check_admin_rights(chat_id=111, user_id=123, session=session)
            
        assert exc_info.value.status_code == 400
        assert "Cannot verify user rights" in exc_info.value.detail

@pytest.mark.asyncio
async def test_check_admin_rights_creates_session_if_none():
    mock_session = AsyncMock()
    
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res
    
    mock_context_maker = MagicMock()
    mock_context_maker.return_value.__aenter__.return_value = mock_session
    mock_context_maker.return_value.__aexit__.return_value = False
    
    with patch("app.db.database.async_session_maker", mock_context_maker), \
         patch.object(settings, "admin_ids", []), \
         patch.object(settings, "system_owner_id", None):
         
        with pytest.raises(HTTPException) as exc_info:
            await check_admin_rights(chat_id=111, user_id=123, session=None)
            
        assert exc_info.value.status_code == 403


