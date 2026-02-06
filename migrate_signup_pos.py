
import asyncio
from sqlalchemy import text
from app.db.database import async_session_maker

async def migrate_signup_position():
    async with async_session_maker() as session:
        print("Migrating: Adding 'position' column to 'signups' table...")
        
        # 1. Check if type 'signup_position_enum' exists or needs creation?
        # Actually, we can reuse 'user_position' enum type if it exists in Postgres, 
        # or easier: use VARCHAR for simplicity in migration to avoid Enum hell, 
        # but SQLAlchemy might expect Enum.
        # Let's try adding column as VARCHAR first to be safe, or TEXT.
        # Wait, the model definition used Enum(Position). modifying it to be strict might be hard.
        # Let's use TEXT in DB and cast in Python? 
        # No, let's try to add it properly.
        
        try:
            # Postgres specific: Add column
            # We assume user_position type exists.
            # But creating a new Enum type 'signup_position_enum' might be safer.
            
            # Simple approach: Add column as VARCHAR/TEXT. 
            # SQLAlchemy Enum can map to VARCHAR if create_constraint=False/native_enum=False?
            # But we are using Postgres native enums usually.
            
            # Let's try adding with the existing 'user_position' type if possible?
            # Or just add as TEXT.
            
            await session.execute(text("ALTER TABLE signups ADD COLUMN IF NOT EXISTS position VARCHAR(10);"))
            await session.commit()
            print("Added 'position' column (VARCHAR).")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            
if __name__ == "__main__":
    asyncio.run(migrate_signup_position())
