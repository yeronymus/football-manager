from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


async def init_models():
    import asyncio
    import logging
    import sys

    logger = logging.getLogger(__name__)
    logger.info("Running database migrations via Alembic...")
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "alembic",
            "upgrade",
            "head",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info("Alembic migrations completed successfully.")
            if stdout:
                logger.info(f"Migrations output:\n{stdout.decode().strip()}")
        else:
            logger.error(f"Alembic migrations failed with exit code {process.returncode}")
            logger.error(f"Error output:\n{stderr.decode().strip()}")
            raise RuntimeError("Alembic upgrade head failed")
    except Exception as e:
        logger.error(f"Failed to run database migrations via Alembic: {e}", exc_info=True)
        logger.warning("Attempting safe fallback to Base.metadata.create_all...")
        import app.db.models  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        stamp_proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "alembic",
            "stamp",
            "head",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await stamp_proc.communicate()
