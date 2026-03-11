import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

async def apply_migration():
    if os.path.exists(".env"):
        load_dotenv(".env")
    
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "debug_password")
    db = os.getenv("POSTGRES_DB", "football_debug")
    host = "localhost" # Changed from db to localhost
    port = os.getenv("POSTGRES_PORT", "5432")
    
    # Construct asyncpg URL
    db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"
    print(f"Connecting to {host}:{port}/{db}...")
    
    engine = create_async_engine(db_url)
    
    async with engine.begin() as conn:
        print("Checking for registration_hours column...")
        # Check if column exists
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='games' AND column_name='registration_hours';
        """)
        result = await conn.execute(check_query)
        column_exists = result.scalar() is not None
        
        if not column_exists:
            print("Adding registration_hours column to games table...")
            await conn.execute(text("ALTER TABLE games ADD COLUMN registration_hours INTEGER DEFAULT 0;"))
            print("Successfully added registration_hours column.")
        else:
            print("Column registration_hours already exists.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(apply_migration())
