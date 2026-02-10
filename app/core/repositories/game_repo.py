from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.repositories.base import BaseRepository
from app.db.models import Game, Signup, SignupStatus, User

class GameRepository(BaseRepository[Game]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Game)

    async def get_active_signups_count(self, game_id: int) -> int:
        result = await self.session.execute(
            select(func.count(Signup.id))
            .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
        )
        return result.scalar() or 0
    
    async def get_signup(self, game_id: int, user_id: int) -> Signup | None:
        result = await self.session.execute(
            select(Signup)
            .where(Signup.game_id == game_id, Signup.user_id == user_id)
        )
        return result.scalar_one_or_none()

    def create_signup(self, game_id: int, user_id: int, status: SignupStatus) -> Signup:
        signup = Signup(game_id=game_id, user_id=user_id, status=status)
        self.session.add(signup)
        return signup
    async def delete_signup(self, signup: Signup) -> None:
        """Deletes a signup record."""
        await self.session.delete(signup)

    async def get_first_reserve(self, game_id: int) -> tuple[Signup, User] | None:
        """Fetch the first reserve player (user data included)."""
        result = await self.session.execute(
            select(Signup, User)
            .join(User)
            .where(Signup.game_id == game_id, Signup.status == SignupStatus.RESERVE)
            .order_by(Signup.created_at)
            .limit(1)
        )
        # Result of execute().first() is a Row object (Signup, User)
        row = result.first()
        if row:
            return row[0], row[1]
        return None

    async def get_active_players(self, game_id: int) -> list[tuple[User, Signup]]:
        """Fetch all active players (User + Signup)."""
        result = await self.session.execute(
            select(User, Signup)
            .join(Signup)
            .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
        )
        return result.all()

    async def get_all_active_and_reserve(self, game_id: int) -> list[Signup]:
        """Fetch all Active and Reserve signups."""
        result = await self.session.execute(
            select(Signup)
            .where(Signup.game_id == game_id, Signup.status.in_([SignupStatus.ACTIVE, SignupStatus.RESERVE]))
        )
        return result.scalars().all()


    async def get_with_lock(self, game_id: int) -> Game | None:
        """Fetch game with FOR UPDATE lock."""
        result = await self.session.execute(
            select(Game).where(Game.id == game_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_game(self, game_id: int) -> Game | None:
        """Fetch game without lock."""
        return await self.session.get(Game, game_id)

    async def get_all_signups_sorted(self, game_id: int) -> list[tuple[Signup, User]]:
        """Fetch all signups (Active + Reserve) sorted by creation time."""
        result = await self.session.execute(
            select(Signup, User)
            .join(User)
            .where(Signup.game_id == game_id)
            .where(Signup.status.in_([SignupStatus.ACTIVE, SignupStatus.RESERVE]))
            .order_by(Signup.created_at.asc())
        )
        return result.all()
