from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from app.db.models import User, Position, GameStats

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: int) -> User | None:
        """Fetch a user by Telegram ID."""
        return await self.session.get(User, user_id)

    async def get_by_id(self, user_id: int) -> User | None:
        """Alias for get_user."""
        return await self.get_user(user_id)

    async def create_user(self, user_id: int, full_name: str, username: str | None, position: Position | str, alt_positions: list[str] = None) -> User:
        """Create a new user. Does not commit automatically to allow transaction grouping."""
        
        # Ensure position is Enum
        if isinstance(position, str):
            # Handle string input (e.g. from API or "CM" default)
            # If string is valid enum value, safe.
            position = Position(position)

        user = User(
            user_id=user_id,
            full_name=full_name,
            username=username,
            player_position=position,
            alt_positions=alt_positions or []
        )
        self.session.add(user)
        return user

    async def update_profile(self, user_id: int, full_name: str = None, position: Position = None, alt_positions: list[str] = None) -> User:
        """Update user profile fields."""
        user = await self.get_user(user_id)
        if not user:
            raise ValueError("User not found")
            
        if full_name:
            user.full_name = full_name
        if position:
            user.player_position = position
        if alt_positions is not None:
            user.alt_positions = alt_positions
            
        return user

    async def get_user_stats(self, user_id: int) -> dict:
        """Calculate aggregate stats for a user."""
        total_goals = await self.session.scalar(
            select(func.sum(GameStats.goals)).where(GameStats.user_id == user_id)
        ) or 0
        
        return {
            "goals": total_goals,
            # Add other stats here later (assists, etc)
        }

    async def search_users(self, query: str) -> list[User]:
        """Search users by name or username (case-insensitive)."""
        clean_query = query.lstrip('@')
        stmt = select(User).where(
            (User.full_name.ilike(f"%{query}%")) | 
            (User.username.ilike(f"%{query}%")) |
            (User.username.ilike(f"%{clean_query}%"))
        ).limit(20)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def merge_users(self, old_user_id: int, new_user_id: int) -> bool:
        """Merges two user accounts by re-assigning all foreign key references from old to new."""
        from app.db.models import Game, Signup, Vote, GameStats, RatingHistory
        
        old_user = await self.get_user(old_user_id)
        new_user = await self.get_user(new_user_id)
        
        if not old_user or not new_user:
             raise ValueError(f"Both users must exist to merge. {old_user_id=} {new_user_id=}")

        # Merge stats (prefer old user's stats since new one is likely fresh)
        new_user.stats_matches = max(new_user.stats_matches or 0, old_user.stats_matches or 0)
        new_user.stats_mvp = max(new_user.stats_mvp or 0, old_user.stats_mvp or 0)
        new_user.games_played = max(new_user.games_played or 0, old_user.games_played or 0)
        
        # Keep old rating if it's different from default, else keep new
        if old_user.rating != 100:
            new_user.rating = old_user.rating

        # 1. Update GameStats 
        await self.session.execute(
             update(GameStats).where(GameStats.user_id == old_user_id).values(user_id=new_user_id)
        )
        
        # 2. Update Signups - Avoid unique constraint (game_id, user_id)
        old_signups = (await self.session.execute(select(Signup).where(Signup.user_id == old_user_id))).scalars().all()
        new_signups = (await self.session.execute(select(Signup).where(Signup.user_id == new_user_id))).scalars().all()
        new_game_ids = {s.game_id for s in new_signups}
        
        for old_s in old_signups:
            if old_s.game_id in new_game_ids:
                # Conflict: both users signed up for the same game. Delete old user's signup
                await self.session.execute(delete(Signup).where(Signup.id == old_s.id))
            else:
                old_s.user_id = new_user_id
                
        # 3. Update Votes - Delete if conflict (voter_id)
        old_votes = (await self.session.execute(select(Vote).where(Vote.voter_id == old_user_id))).scalars().all()
        new_votes = (await self.session.execute(select(Vote).where(Vote.voter_id == new_user_id))).scalars().all()
        new_vote_keys = {(v.game_id, v.vote_team) for v in new_votes}
        
        for old_v in old_votes:
            if (old_v.game_id, old_v.vote_team) in new_vote_keys:
                await self.session.execute(delete(Vote).where(Vote.id == old_v.id))
            else:
                old_v.voter_id = new_user_id
                
        # Target ID for votes has no unique constraint constraint
        await self.session.execute(update(Vote).where(Vote.target_id == old_user_id).values(target_id=new_user_id))
        
        # 4. Update Games created
        await self.session.execute(update(Game).where(Game.created_by == old_user_id).values(created_by=new_user_id))
        
        # 5. Rating History
        await self.session.execute(update(RatingHistory).where(RatingHistory.user_id == old_user_id).values(user_id=new_user_id))
        
        # 6. Delete old user
        await self.session.execute(delete(User).where(User.user_id == old_user_id))
        
        return True
