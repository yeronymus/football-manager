from typing import List, Tuple
from app.db.models import User, Position, Team
import random

class Player:
    def __init__(self, user: User):
        self.user = user
        self.rating = user.rating
        self.position = user.position
        self.id = user.user_id

def balance_teams(players: List[User]) -> Tuple[List[User], List[User]]:
    """
    Balances teams using Snake Draft and Swap Optimization.
    Returns (Team A, Team B).
    """
    # 1. Separate Goalkeepers
    gks = [p for p in players if p.position == Position.GK]
    field_players = [p for p in players if p.position != Position.GK]

    team_a = []
    team_b = []

    # Distribute GKs first
    # Sort GKs by rating to distribute evenly if multiple
    gks.sort(key=lambda x: x.rating, reverse=True)
    for i, gk in enumerate(gks):
        if i % 2 == 0:
            team_a.append(gk)
        else:
            team_b.append(gk)

    # 2. Sort field players by rating
    field_players.sort(key=lambda x: x.rating, reverse=True)

    # 3. Snake Draft for field players
    # We need to account for current team sizes (due to GKs)
    # But Snake Draft usually resets order. 
    # Let's just continue filling based on current count or just alternate.
    # Standard Snake: 1->A, 2->B, 3->B, 4->A...
    
    # If GKs made teams uneven, we might need to adjust start.
    # Let's assume we want equal size if possible.
    
    for i, player in enumerate(field_players):
        # Determine turn based on snake draft pattern
        # 0, 3, 4, 7... -> Team A
        # 1, 2, 5, 6... -> Team B
        # Pattern repeats every 4: A, B, B, A
        
        remainder = i % 4
        if remainder == 0 or remainder == 3:
            # Prefer team with fewer players if significantly unbalanced?
            # For now, stick to snake draft logic which naturally balances strength
            team_a.append(player)
        else:
            team_b.append(player)

    # 4. Swap Optimization (Micro-correction)
    # Try to swap players between teams to minimize rating difference
    # Limit iterations to avoid infinite loops
    
    def get_avg_rating(team):
        if not team: return 0
        return sum(p.rating for p in team) / len(team)

    best_diff = abs(get_avg_rating(team_a) - get_avg_rating(team_b))
    
    # Simple Hill Climbing: Try random swaps and keep if better
    # Or iterate through pairs.
    # Since N is small (15 players), we can try swapping every pair of field players.
    
    # Identify field players in each team (don't swap GKs)
    field_a = [p for p in team_a if p.position != Position.GK]
    field_b = [p for p in team_b if p.position != Position.GK]
    
    improved = True
    while improved:
        improved = False
        current_diff = abs(get_avg_rating(team_a) - get_avg_rating(team_b))
        
        best_swap = None
        
        for p_a in field_a:
            for p_b in field_b:
                # Calculate new diff if swapped
                # Remove p_a, add p_b to A
                new_sum_a = sum(p.rating for p in team_a) - p_a.rating + p_b.rating
                new_avg_a = new_sum_a / len(team_a)
                
                new_sum_b = sum(p.rating for p in team_b) - p_b.rating + p_a.rating
                new_avg_b = new_sum_b / len(team_b)
                
                new_diff = abs(new_avg_a - new_avg_b)
                
                if new_diff < current_diff:
                    current_diff = new_diff
                    best_swap = (p_a, p_b)
        
        if best_swap:
            p_a, p_b = best_swap
            # Perform swap in main lists
            team_a.remove(p_a)
            team_a.append(p_b)
            team_b.remove(p_b)
            team_b.append(p_a)
            
            # Update field lists
            field_a.remove(p_a)
            field_a.append(p_b)
            field_b.remove(p_b)
            field_b.append(p_a)
            
            improved = True # Continue optimizing

    return team_a, team_b
