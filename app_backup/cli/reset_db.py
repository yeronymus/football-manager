import asyncio
import sys
import os

# Add parent directory to path to import app modules
sys.path.append(os.getcwd())

from app.db.database import engine
from app.db.models import Base
from sqlalchemy import text

async def reset_database():
    print("🔥 NUKING THE DATABASE...")
    async with engine.begin() as conn:
        # Drop all tables
        # For Postgres, confirm drop cascade might be needed but drop_all usually handles it if metadata is correct
        # BUT `Base.metadata.drop_all` might fail if there are tables NOT in metadata.
        # Safer to dropping schema public CASCADE? (Too dangerous for shared DB).
        # Let's try drop_all first.
        try:
            await conn.run_sync(Base.metadata.drop_all)
            print("✅ All tables dropped.")
        except Exception as e:
            print(f"❌ Error dropping tables: {e}")
            
        # Recreate
        try:
            await conn.run_sync(Base.metadata.create_all)
            print("✅ All tables recreated.")
        except Exception as e:
            print(f"❌ Error creating tables: {e}")

    await engine.dispose()

if __name__ == "__main__":
    if "--force" in sys.argv:
        asyncio.run(reset_database())
    else:
        print("To reset DB, run with --force")
