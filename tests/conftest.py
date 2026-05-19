import pytest
import asyncio
from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base
from app.db.models import User

# SQLite does not support PostgreSQL ARRAY type natively.
# We patch User.alt_positions to use JSON type when running tests on SQLite.
User.__table__.columns['alt_positions'].type = JSON()

@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def session():
    # Use SQLite in-memory database for fast, fully isolated unit tests
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        
    await test_engine.dispose()
