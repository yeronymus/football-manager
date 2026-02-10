from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.models import User, Position, GameStats

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: int) -> User | None:
        """Fetch a user by Telegram ID."""
        return await self.session.get(User, user_id)

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
        stmt = select(User).where(
            (User.full_name.ilike(f"%{query}%")) | 
            (User.username.ilike(f"%{query}%"))
        ).limit(20)
        result = await self.session.execute(stmt)
        return result.scalars().all()
