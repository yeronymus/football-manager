from typing import List, Tuple
from app.db.models import User

def calculate_expected_score(player_rating: int, opponent_rating: int) -> float:
    return 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))

def calculate_new_rating(player: User, opponent_avg_rating: int, actual_score: float, is_mvp: bool) -> int:
    """
    Calculates new rating for a player.
    """
    # K-factor logic
    k_factor = 50 if player.games_played < 5 else 25
    
    expected_score = calculate_expected_score(player.rating, opponent_avg_rating)
    
    # Base change
    rating_change = k_factor * (actual_score - expected_score)
    
    # MVP Bonus
    if is_mvp:
        if actual_score == 1: # Win
            rating_change += 10 # +35 total (approx if base is 25)
        elif actual_score == 0: # Loss
            rating_change += 20 # -5 total (approx if base is -25)
            
    new_rating = player.rating + int(rating_change)
    return new_rating
