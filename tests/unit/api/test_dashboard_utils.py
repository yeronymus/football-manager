import pytest
from app.api.routers.dashboard import clean_location

def test_clean_location_empty():
    assert clean_location("") == ""
    assert clean_location(None) is None

def test_clean_location_simple():
    assert clean_location("Strahov") == "Strahov"

def test_clean_location_with_url():
    assert clean_location("Strahov (https://maps.google.com/xyz)") == "Strahov"
    assert clean_location("Aritma http://maps.cz/123") == "Aritma"

def test_clean_location_whitespace():
    assert clean_location("  Strahov  ") == "Strahov"
    assert clean_location("Strahov (https://maps.google.com/xyz)  ") == "Strahov"
