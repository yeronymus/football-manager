import asyncio
import sys
import os
import traceback

# Add project root to path
sys.path.append(os.getcwd())

try:
    from sqlalchemy import text
    from app.db.database import async_session_maker
except ImportError as e:
    print(f"Import Error: {e}", file=sys.stderr)
    sys.exit(1)

async def inspect():
    try:
        async with async_session_maker() as session:
            print("--- Existing Games ---")
            result = await session.execute(text("SELECT id, status, created_at FROM games ORDER BY id"))
            games = result.fetchall()
            for g in games:
                print(f"ID: {g[0]} | Status: {g[1]} | Created: {g[2]}")

            print("\n--- Sequence Value ---")
            try:
                # PostgreSQL sequence name usually table_column_seq
                seq_res = await session.execute(text("SELECT last_value FROM games_id_seq"))
                print(f"Current Sequence Value: {seq_res.scalar()}")
            except Exception as e:
                print(f"Could not read sequence: {e}")
    except Exception as e:
        print(f"DB Error: {e}", file=sys.stderr)
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(inspect())
    except Exception as e:
        print(f"Main Error: {e}", file=sys.stderr)
        traceback.print_exc()
