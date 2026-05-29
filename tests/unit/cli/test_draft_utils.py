import pytest
from app.cli.draft import calc_win_pct

def test_calc_win_pct_zero_total():
    assert calc_win_pct(0, 0, 0) == "-"

def test_calc_win_pct_success():
    # 1 win, 1 draw, 1 loss = 3 total. 1/3 = 33.33% -> 33%
    assert calc_win_pct(1, 1, 1) == "33%"
    
    # 2 wins, 0 draw, 0 loss = 2 total. 2/2 = 100%
    assert calc_win_pct(2, 0, 0) == "100%"
    
    # 0 wins, 0 draw, 2 loss = 2 total. 0/2 = 0%
    assert calc_win_pct(0, 0, 2) == "0%"

def test_calc_win_pct_draws_included():
    # 1 win, 2 draws, 1 loss = 4 total. 1/4 = 25%
    assert calc_win_pct(1, 2, 1) == "25%"
