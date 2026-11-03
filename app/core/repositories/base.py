from typing import Any, Generic, List, Optional, Type, TypeVar

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class BaseRepository(Generic[ModelType]):
    """
    Base generic repository providing standard CRUD operations across single-column PK models.
    """

    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        self.session = session
        self.model = model

    def _primary_key_column(self):
        pk_cols = sa_inspect(self.model).primary_key
        if len(pk_cols) != 1:
            raise ValueError(
                f"get_with_lock requires a single-column primary key on {self.model.__name__}"
            )
        return pk_cols[0]

    async def get(self, id: Any) -> Optional[ModelType]:
        return await self.session.get(self.model, id)

    async def get_by_id(self, id: Any) -> Optional[ModelType]:
        return await self.get(id)

    async def get_with_lock(self, id: Any) -> Optional[ModelType]:
        """Fetch with SELECT FOR UPDATE using the model's actual primary key column."""
        pk_col = self._primary_key_column()
        result = await self.session.execute(
            select(self.model).where(pk_col == id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> List[ModelType]:
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    def add(self, obj: ModelType) -> ModelType:
        """Adds a database object to the current session."""
        self.session.add(obj)
        return obj

    async def delete_by_id(self, id: Any) -> bool:
        obj = await self.get(id)
        if obj:
            await self.session.delete(obj)
            return True
        return False
