import asyncio
import os
import sys
from sqlalchemy import text
from app.db.database import async_session_maker

async def add_vote_team_column():
    print("CHECKING/ADDING 'vote_team' column to 'votes' table...")
    async with async_session_maker() as session:
        try:
            # Check if column exists is hard in raw SQL without querying schema,
            # but Postgres supports IF NOT EXISTS for ADD COLUMN in newer versions?
            # Actually, standard SQL doesn't support IF NOT EXISTS for column.
            # Best way: Try to select it. If fails, add it.
            try:
                await session.execute(text("SELECT vote_team FROM votes LIMIT 1"))
                print("Column 'vote_team' already exists.")
            except Exception:
                print("Column 'vote_team' MISSING. Adding...")
                await session.rollback() # Clear formatting error state
                
                # Add column
                # We need to handle the ENUM type casting or just use VARCHAR for simplicity if ENUM is issue.
                # In models.py it is Enum(Team).
                # Let's add it as VARCHAR(10) to be safe, or cast via type.
                # Actually, models.py says: vote_team = Column(Enum(Team, name="vote_team_enum"), nullable=False)
                # So we may need to create the type first.
                
                try:
                    await session.execute(text("CREATE TYPE vote_team_enum AS ENUM ('A', 'B', 'C')"))
                except:
                    await session.rollback() # Likely exists
                    pass
                
                await session.execute(text("ALTER TABLE votes ADD COLUMN vote_team vote_team_enum"))
                await session.commit()
                print("✅ Column 'vote_team' added successfully!")
                
        except Exception as e:
            print(f"❌ Failed to add column: {e}")

if __name__ == "__main__":
    asyncio.run(add_vote_team_column())
