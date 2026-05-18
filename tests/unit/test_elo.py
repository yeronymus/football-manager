import pytest
from app.bot.elo import calculate_expected_score, calculate_new_rating

def test_calculate_expected_score_equal_ratings():
    assert calculate_expected_score(1000, 1000) == 0.5

def test_calculate_expected_score_higher_player_rating():
    expected = calculate_expected_score(1200, 1000)
    assert expected > 0.5
    assert round(expected, 4) == 0.7597

def test_calculate_expected_score_lower_player_rating():
    expected = calculate_expected_score(1000, 1200)
    assert expected < 0.5
    assert round(expected, 4) == 0.2403

def test_calculate_new_rating_win():
    # Win = +10
    new_rating = calculate_new_rating(100, 100, 1.0, False)
    assert new_rating == 110

def test_calculate_new_rating_loss():
    # Loss = -5
    new_rating = calculate_new_rating(100, 100, 0.0, False)
    assert new_rating == 95

def test_calculate_new_rating_mvp_only():
    # MVP only (no win/loss) = +5
    new_rating = calculate_new_rating(100, 100, 0.5, True)
    assert new_rating == 105

def test_calculate_new_rating_win_and_mvp():
    # Win (+10) + MVP (+5) = +15
    new_rating = calculate_new_rating(100, 100, 1.0, True)
    assert new_rating == 115

def test_calculate_new_rating_loss_and_mvp():
    # Loss (-5) + MVP (+5) = 0 change
    new_rating = calculate_new_rating(100, 100, 0.0, True)
    assert new_rating == 100

def test_calculate_new_rating_floor_zero():
    # Loss = -5. 2 - 5 = -3, but floor is 0.
    new_rating = calculate_new_rating(2, 100, 0.0, False)
    assert new_rating == 0
