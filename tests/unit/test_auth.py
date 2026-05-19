import pytest
from fastapi import HTTPException
from app.api.auth import get_user_from_init_data
import urllib.parse

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
