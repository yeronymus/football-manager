import datetime
import pytest
from app.api.routers.admin import _interpret_prague_tz, _should_publish_game_now

def test_interpret_prague_tz_naive():
    naive_dt = datetime.datetime(2026, 6, 20, 12, 0, 0)
    interpreted = _interpret_prague_tz(naive_dt)
    assert interpreted is not None
    assert interpreted.tzinfo is not None
    assert interpreted.tzinfo.key == "Europe/Prague"
    assert interpreted.year == 2026
    assert interpreted.hour == 12

def test_interpret_prague_tz_aware():
    tz = datetime.timezone.utc
    aware_dt = datetime.datetime(2026, 6, 20, 12, 0, 0, tzinfo=tz)
    interpreted = _interpret_prague_tz(aware_dt)
    assert interpreted == aware_dt
    assert interpreted.tzinfo == tz

def test_interpret_prague_tz_none():
    assert _interpret_prague_tz(None) is None

def test_should_publish_game_now_immediate():
    # Game is in the future, publish_at is in the past -> True
    game_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
    publish_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    assert _should_publish_game_now(game_dt, publish_at) is True

def test_should_publish_game_now_delayed():
    # Game is in the future, publish_at is in the future -> False
    game_dt = datetime.timezone.utc
    future_game_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)
    publish_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
    assert _should_publish_game_now(future_game_dt, publish_at) is False

def test_should_publish_game_now_past_game():
    # Game is in the past -> False
    past_game_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    publish_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
    assert _should_publish_game_now(past_game_dt, publish_at) is False
