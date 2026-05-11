from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Game, User, Signup, SignupStatus, RatingHistory, Team, GameStats, PlayerProfile
import logging

logger = logging.getLogger(__name__)

class StatsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def revert_stats(self, game_id: int):
        """Reverts stats for a game (if reverting from finished)."""
        # Fetch game to know its chat_id
        game_obj = await self.session.get(Game, game_id)
        if not game_obj: return
        
        # 1. Revert Ratings & Games Played
        history_result = await self.session.execute(select(RatingHistory).where(RatingHistory.game_id == game_id))
        histories = history_result.scalars().all()
        for h in histories:
            user = await self.session.get(User, h.user_id)
            if user and h.old_rating is not None:
                user.rating = h.old_rating
                user.games_played = max(0, user.games_played - 1)
                user.stats_matches = max(0, user.stats_matches - 1)
            
            profile = await self.session.scalar(select(PlayerProfile).where(
                PlayerProfile.user_id == h.user_id, 
                PlayerProfile.chat_id == game_obj.chat_id
            ))
            if profile and h.old_rating is not None:
                profile.rating = h.old_rating
                profile.games_played = max(0, profile.games_played - 1)
                profile.stats_matches = max(0, profile.stats_matches - 1)

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
                profile = await self.session.scalar(select(PlayerProfile).where(
                    PlayerProfile.user_id == s.user_id, 
                    PlayerProfile.chat_id == game_obj.chat_id
                ))
                if profile:
                    profile.stats_mvp = max(0, profile.stats_mvp - 1)
            # We don't delete GameStats here if caller does it?
            # Caller `GameService.finish_game` deleted them.
            # So pass. Caller manages `GameStats` table.
            
    async def apply_game_results(self, game: Game, mvp_ids: set[int]):
        """
        Calculates and applies rating changes, updates user stats, and records history.
        Assumes GameStats (goals) already saved by caller.
        """
        # Determine Ranks and Points for players
        team_points = {} # Team -> Base Point Change

        # Универсальный алгоритм распределения очков (работает для 2, 3, 4+ команд)
        # 1-е место: +10 очков
        # Последнее место: -5 очков
        # Остальные места: равномерно распределены между +10 и -5
        
        scores_map = {}
        if game.team_count >= 2:
            scores_map[Team.A] = game.score_a or 0
            scores_map[Team.B] = game.score_b or 0
        if game.team_count >= 3:
            scores_map[Team.C] = game.score_c or 0
        
        # Sort teams by score descending
        sorted_teams = sorted(scores_map.items(), key=lambda item: item[1], reverse=True)
        
        # Find unique scores to determine ties
        unique_scores = sorted(list(set(scores_map.values())), reverse=True)
        
        for team, score in sorted_teams:
            if len(unique_scores) == 1:
                # All teams tied
                team_points[team] = 0
            else:
                rank = unique_scores.index(score)
                # Map rank (0 to len(unique_scores)-1) to points (+10 to -5)
                # Max points: 10, Min points: -5
                max_rank = len(unique_scores) - 1
                points = 10 - (15 * rank / max_rank)
                team_points[team] = round(points)
        
        # Fetch all active players with their teams AND profiles
        result = await self.session.execute(
            select(User, Signup.team, PlayerProfile)
            .join(Signup, User.user_id == Signup.user_id)
            .outerjoin(PlayerProfile, (User.user_id == PlayerProfile.user_id) & (PlayerProfile.chat_id == game.chat_id))
            .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
        )
        players_data = result.all() # List of (User, Team, PlayerProfile)
        
        for user, team, profile in players_data:
            if not profile:
                profile = PlayerProfile(user_id=user.user_id, chat_id=game.chat_id)
                self.session.add(profile)
                
            old_rating = profile.rating or 100
            
            # Get base change from team_points
            change = team_points.get(team, -5) # Default to -5 if team unassigned (safety)
            
            is_mvp = (user.user_id in mvp_ids)
            if is_mvp:
                change += 5
            
            # Update Profile
            profile.rating = (profile.rating or 100) + change
            profile.games_played = (profile.games_played or 0) + 1
            profile.stats_matches = (profile.stats_matches or 0) + 1
            if is_mvp:
                profile.stats_mvp = (profile.stats_mvp or 0) + 1
                
            # We no longer overwrite global user.rating!
            # Keep global games_played and MVP for legacy compatibility
            user.games_played = (user.games_played or 0) + 1
            user.stats_matches = (user.stats_matches or 0) + 1
            if is_mvp:
                user.stats_mvp = (user.stats_mvp or 0) + 1
            
            # Record History
            self.session.add(RatingHistory(
                user_id=user.user_id,
                game_id=game.id,
                old_rating=old_rating,
                new_rating=profile.rating,
                change=change
            ))

