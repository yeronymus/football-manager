from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Game, User, Signup, SignupStatus, RatingHistory, Team, GameStats
import logging

logger = logging.getLogger(__name__)

class StatsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def revert_stats(self, game_id: int):
        """Reverts stats for a game (if reverting from finished)."""
        # 1. Revert Ratings & Games Played
        history_result = await self.session.execute(select(RatingHistory).where(RatingHistory.game_id == game_id))
        histories = history_result.scalars().all()
        for h in histories:
            user = await self.session.get(User, h.user_id)
            if user and h.old_rating is not None:
                user.rating = h.old_rating
                user.games_played = max(0, user.games_played - 1)
                user.stats_matches = max(0, user.stats_matches - 1)
            await self.session.delete(h)
            
        # 2. Revert MVP Counts (GameStats handled by caller? Or here?)
        # GameService handles GameStats creation/deletion usually?
        # If we move logic here, we should handle it.
        # But GameStats contains Goals too.
        # Let's assume Caller handles GameStats lifecycle (deletion), 
        # BUT we must revert User MVP counters.
        stats_result = await self.session.execute(select(GameStats).where(GameStats.game_id == game_id))
        stats = stats_result.scalars().all()
        for s in stats:
            if s.is_mvp:
                user = await self.session.get(User, s.user_id)
                if user:
                    user.stats_mvp = max(0, user.stats_mvp - 1)
            # We don't delete GameStats here if caller does it?
            # Caller `GameService.finish_game` deleted them.
            # So pass. Caller manages `GameStats` table.
            
    async def apply_game_results(self, game: Game, mvp_ids: set[int]):
        """
        Calculates and applies rating changes, updates user stats, and records history.
        Assumes GameStats (goals) already saved by caller.
        """
        # Determine Ranks for 3-team games
        ranking = []
        if game.team_count == 3:
            scores = [
                (Team.A, game.score_a or 0),
                (Team.B, game.score_b or 0),
                (Team.C, game.score_c or 0)
            ]
            scores.sort(key=lambda x: x[1], reverse=True)
            ranking = [s[0] for s in scores] # [1st, 2nd, 3rd]

        # Fetch all active players with their teams
        result = await self.session.execute(
            select(User, Signup.team)
            .join(Signup)
            .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
        )
        players_data = result.all() # List of (User, Team)
        
        for user, team in players_data:
            old_rating = user.rating
            change = -5 # Default
            
            if game.team_count == 2:
                if team == game.winner_team:
                    change = 10
                else:
                    change = -5
            else:
                # 3 Teams logic: 1st:+10, 2nd:0, 3rd:-5
                if team == ranking[0]:
                    change = 10
                elif team == ranking[1]:
                    change = 0
                else:
                    change = -5
            
            is_mvp = (user.user_id in mvp_ids)
            if is_mvp:
                change += 5
                # Note: User stats_mvp incremented by Caller when saving GameStats? 
                # Or should we do it?
                # GameService.finish_game does it.
                # If we move it here, we need to know if we should increment.
                # Let's rely on Caller for `GameStats` and `User.stats_mvp` for now, 
                # OR move full responsibility here.
                # Better: StatsService handles ALL User stat updates.
                # But `GameStats` record creation requires Input Data (goals).
                # So Caller creates `GameStats`, `StatsService` updates `User` and `RatingHistory`.
            
            user.rating += change
            user.games_played += 1
            user.stats_matches += 1
            
            # Record History
            self.session.add(RatingHistory(
                user_id=user.user_id,
                game_id=game.id,
                old_rating=old_rating,
                new_rating=user.rating,
                change=change
            ))
