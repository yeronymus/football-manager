from typing import List, Tuple
from app.db.models import User

def calculate_expected_score(player_rating: int, opponent_rating: int) -> float:
    return 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))

from app.config import settings

def calculate_new_rating(player: User, opponent_avg_rating: int, actual_score: float, is_mvp: bool) -> int:
    """
    Calculates new rating for a player.
    """
    """
    Calculates new rating based on static points system.
    Win: +10
    Loss: -5
    MVP: +5
    """
    rating_change = 0
    
    # Base change
    if actual_score == 1: # Win
        rating_change = 10
    elif actual_score == 0: # Loss
        rating_change = -5
    
    # MVP Bonus
    if is_mvp:
        rating_change += 5
            
    new_rating = player.rating + int(rating_change)
    return max(0, new_rating) # Prevent negative rating? User didn't specify, but safer.
