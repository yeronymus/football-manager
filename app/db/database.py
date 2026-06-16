from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=settings.debug,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True  # Helpful for Proxmox/LXC environments where connections might be dropped
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
        # Run "alembic upgrade head" using the current python executable to guarantee venv compatibility
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "alembic", "upgrade", "head",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
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
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
