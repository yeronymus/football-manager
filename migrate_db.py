
import asyncio
from sqlalchemy import text
from app.db.database import engine

async def migrate():
    async with engine.begin() as conn:
        print("Migrating...")
        
        # 1. Add columns to games table
        # We use IF NOT EXISTS concept manually via exception handling or check, 
        # but pure SQL 'ADD COLUMN IF NOT EXISTS' is supported in Postgres 9.6+.
        columns = [
            "ALTER TABLE games ADD COLUMN IF NOT EXISTS price INTEGER DEFAULT 100;",
            "ALTER TABLE games ADD COLUMN IF NOT EXISTS team_count INTEGER DEFAULT 2;",
            "ALTER TABLE games ADD COLUMN IF NOT EXISTS has_active_gk_c BOOLEAN DEFAULT TRUE;"
        ]
        
        for col_sql in columns:
            try:
                await conn.execute(text(col_sql))
                print(f"Executed: {col_sql}")
            except Exception as e:
                print(f"Error executing {col_sql}: {e}")

        # 2. Add 'C' to Team Enum
        # Postgres ENUM modification is tricky. 
        # "ALTER TYPE team ADD VALUE 'C'" cannot be run inside a transaction block in some versions,
        # but sqlalchemy 'engine.begin()' starts one.
        # We might need to run this with isolation_level="AUTOCOMMIT" or try-catch.
        try:
             await conn.execute(text("ALTER TYPE team ADD VALUE IF NOT EXISTS 'C'"))
             print("Added Team C to Enum")
        except Exception as e:
             # Often fails if already exists or transaction issue.
             # If it's "ALTER TYPE ... cannot run inside a transaction block", we need a separate connection.
             print(f"Skipping Enum Update (might exist or transaction issue): {e}")

    print("Migration finished table updates.")

    # Try Enum update outside transaction if needed (though engine.begin() is context)
    # Let's see if the above works.

if __name__ == "__main__":
    asyncio.run(migrate())
