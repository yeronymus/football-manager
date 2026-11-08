import inspect
from typing import Any, Callable, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories.announcement_repository import AnnouncementRepository
from app.core.repositories.disciplinary_repository import DisciplinaryRepository
from app.core.repositories.game_repo import GameRepository
from app.core.repositories.signup_repository import SignupRepository
from app.core.repositories.stats_repository import StatsRepository
from app.core.repositories.tenant_repository import TenantRepository
from app.core.repositories.user_repository import UserRepository
from app.core.repositories.vote_repository import VoteRepository
from app.db.database import async_session_maker


class UnitOfWork:
    """
    Provides transaction atomicity (Unit of Work pattern) with post-commit cache
    eviction and domain event outbox hooks (ADR-05).
    Ensures all repositories share the same database session within an 'async with' block,
    guarantees rollback on exception, and executes deferred cache evictions and post-commit
    callbacks strictly AFTER the database transaction commits.
    """

    def __init__(self, session_factory=async_session_maker, session: AsyncSession | None = None):
        self._session_factory = session_factory
        self._session: AsyncSession | None = session
        self._external_session = session is not None
        self._deferred_cache_keys: List[str] = []
        self._post_commit_callbacks: List[Callable[[], Any]] = []

    async def __aenter__(self) -> "UnitOfWork":
        if not self._session:
            self._session = self._session_factory()

        self.game_repo = GameRepository(self._session)
        self.user_repo = UserRepository(self._session)
        self.tenant_repo = TenantRepository(self._session)
        self.signup_repo = SignupRepository(self._session)
        self.vote_repo = VoteRepository(self._session)
        self.disciplinary_repo = DisciplinaryRepository(self._session)
        self.stats_repo = StatsRepository(self._session)
        self.announcement_repo = AnnouncementRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            if exc_type:
                await self.rollback()
            if not self._external_session:
                await self._session.close()

    def defer_cache_eviction(self, key: str) -> None:
        """Schedules a Redis cache key to be evicted immediately after `commit()`."""
        if key and key not in self._deferred_cache_keys:
            self._deferred_cache_keys.append(key)

    def defer_post_commit(self, callback: Callable[[], Any]) -> None:
        """Registers a callback or coroutine function to run after `commit()`."""
        self._post_commit_callbacks.append(callback)

    async def commit(self):
        if self._session:
            await self._session.commit()

        # Execute post-commit cache evictions so concurrent readers never re-populate stale pre-commit rows
        if self._deferred_cache_keys:
            from app.core.services.cache import cache_service

            keys = list(self._deferred_cache_keys)
            self._deferred_cache_keys.clear()
            for key in keys:
                await cache_service.evict(key)

        if self._post_commit_callbacks:
            callbacks = list(self._post_commit_callbacks)
            self._post_commit_callbacks.clear()
            for cb in callbacks:
                res = cb()
                if inspect.isawaitable(res):
                    await res

    async def rollback(self):
        self._deferred_cache_keys.clear()
        self._post_commit_callbacks.clear()
        if self._session:
            await self._session.rollback()

    @property
    def session(self) -> AsyncSession:
        if not self._session:
            raise RuntimeError("UnitOfWork not started. Use 'async with uow:'")
        return self._session
