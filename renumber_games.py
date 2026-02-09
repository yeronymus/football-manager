
import asyncio
import sys
import os

# Add /app to sys.path
sys.path.append('/app')

try:
    from sqlalchemy import text
    from app.db.database import async_session_maker
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}", file=sys.stderr)
    sys.exit(1)

async def renumber():
    print("Starting renumbering...", file=sys.stderr)
    try:
        async with async_session_maker() as session:
            # 1. Disable constraints (if any hard ones, usually ok with cascade but let's be safe)
            # Actually, we should just update IDs. 
            # Order matters to avoid collision. 
            # Logic: 2->999, 44->1, 45->2, 46->3, 999->4
            
            # Map: {OldID: NewID}
            # We must do this carefully.
            
            # Step 1: Move 2 to 999 (Temp) to free up 2 for 45
            print("Moving Game 2 -> 999...", file=sys.stderr)
            await session.execute(text("UPDATE games SET id=999 WHERE id=2"))
            
            # Step 2: Move 44 -> 1
            print("Moving Game 44 -> 1...", file=sys.stderr)
            await session.execute(text("UPDATE games SET id=1 WHERE id=44"))
            
            # Step 3: Move 45 -> 2
            print("Moving Game 45 -> 2...", file=sys.stderr)
            await session.execute(text("UPDATE games SET id=2 WHERE id=45"))
            
            # Step 4: Move 46 -> 3
            print("Moving Game 46 -> 3...", file=sys.stderr)
            await session.execute(text("UPDATE games SET id=3 WHERE id=46"))
            
            # Step 5: Move 999 -> 4
            print("Moving Game 999 -> 4...", file=sys.stderr)
            await session.execute(text("UPDATE games SET id=4 WHERE id=999"))
            
            # Step 6: Reset Sequence to 5
            print("Resetting sequence to 5...", file=sys.stderr)
            await session.execute(text("ALTER SEQUENCE games_id_seq RESTART WITH 5"))
            
            await session.commit()
            print("Renumbering complete!", file=sys.stderr)
            
    except Exception as e:
        print(f"Error renumbering: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(renumber())
