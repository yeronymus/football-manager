
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_session_maker
from app.core.repositories.game_repo import GameRepository
from app.core.repositories.user_repository import UserRepository

class UnitOfWork:
    """
    Provides transaction atomicity (Unit of Work pattern).
    Ensures all repositories share the same database session within an 'async with' block.
    """
    def __init__(self, session_factory=async_session_maker, session: AsyncSession | None = None):
        self._session_factory = session_factory
        self._session: AsyncSession | None = session
        self._external_session = session is not None
        
    async def __aenter__(self) -> "UnitOfWork":
        if not self._session:
            self._session = self._session_factory()
            
        # IMPORTANT: Pass the same session to all repositories
        self.game_repo = GameRepository(self._session)
        self.user_repo = UserRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session and not self._external_session:
            if exc_type:
                await self.rollback()
            await self._session.close()

    async def commit(self):
        if self._session:
            await self._session.commit()

    async def rollback(self):
        if self._session:
            await self._session.rollback()

    @property
    def session(self) -> AsyncSession:
        if not self._session:
            raise RuntimeError("UnitOfWork not started. Use 'async with uow:'")
        return self._session
