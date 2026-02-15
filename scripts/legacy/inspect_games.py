
import asyncio
import sys
import os

print(f"DEBUG: sys.path before: {sys.path}", file=sys.stderr)
sys.path.append('/app')

try:
    from sqlalchemy import select
    from app.db.database import async_session_maker
    from app.db.models import Game, GameStatus
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}", file=sys.stderr)
    sys.exit(1)

async def inspect():
    try:
        print("Connecting to DB...", file=sys.stderr)
        async with async_session_maker() as session:
            print("Connected. Querying...", file=sys.stderr)
            stmt = select(Game).order_by(Game.id)
            res = await session.execute(stmt)
            games = res.scalars().all()
            
            print(f"{'ID':<5} | {'Date':<16} | {'Status':<10} | {'Location'}")
            print("-" * 60)
            
            for g in games:
                dt_str = g.date_time.strftime("%Y-%m-%d %H:%M") if g.date_time else "None"
                status = g.status.value if hasattr(g.status, 'value') else str(g.status)
                loc = g.location or "Unknown"
                print(f"{g.id:<5} | {dt_str:<16} | {status:<10} | {loc}")
                
    except Exception as e:
        print(f"Error inspecting games: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(inspect())
