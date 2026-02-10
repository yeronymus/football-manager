from typing import Self
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_session_maker
from app.core.repositories.game_repo import GameRepository

class UnitOfWork:
    """
    Unit of Work pattern to handle transactions atomically.
    Serves as a factory for Repositories ensuring they share the same session.
    """
    def __init__(self, session_factory=async_session_maker):
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        
    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        # Initialize Repositories with shared session
        self.game_repo = GameRepository(self._session)
        # Add other repositories here as they are created
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
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
