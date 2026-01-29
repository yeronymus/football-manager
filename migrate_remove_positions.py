import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

# Ensure we use localhost if running locally with our script overrides, 
# but usually settings load from env. 
# We'll just trust settings if it works for other scripts, or override if needed.

async def migrate_users():
    print(f"Connecting to {settings.DATABASE_URL}")
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        print("Migrating users from CAM/CDM to CM...")
        
        # Update CAM -> CM
        await conn.execute(text("UPDATE users SET player_position = 'CM' WHERE player_position = 'CAM'"))
        
        # Update CDM -> CM
        await conn.execute(text("UPDATE users SET player_position = 'CM' WHERE player_position = 'CDM'"))
        
        # Also clean up alt_positions array if it contains CAM/CDM
        await conn.execute(text("UPDATE users SET alt_positions = array_remove(alt_positions, 'CAM')"))
        await conn.execute(text("UPDATE users SET alt_positions = array_remove(alt_positions, 'CDM')"))
        # Ideally add CM if it was there? For now just removing is safe. 
        # Actually user likely wants CM if they had CAM. 
        # But we updated primary position. For alts, let's just remove invalid ones.

        # Now we need to remove values from the ENUM logic in Postgres.
        # Postgres doesn't allow removing enum values easily without recreating the type.
        # However, for the application logic (Python), they are gone.
        # We can leave the enum values in DB to avoid complex migration (create new type, convert, drop old).
        # Important is that no rows use it, which we ensured above.
        
        print("Migration complete. Enum values CAM/CDM still exist in DB definition but are unused.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_users())
