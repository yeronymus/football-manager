import asyncio
from app.db.database import async_session_maker
from app.db.models import Game
from sqlalchemy import select
import re

def clean_location(loc: str) -> str:
    if not loc: return loc
    return re.sub(r'\(?https?://[^\s)]+\)?', '', loc).strip()

async def run():
    async with async_session_maker() as session:
        res = await session.execute(select(Game))
        games = res.scalars().all()
        for g in games:
            cleaned = clean_location(g.location)
            if cleaned != g.location:
                g.location = cleaned
                print(f"Cleaned location for Game {g.id}")
            
            # Fix team_count if they only have score A and B and no C, and max_players <= 14? 
            # The user said: "в три команды турнир мы катали только первую игру".
            # So if it's not the first game, or if max_players <= 18?
            # Better to fix team_count = 2 for any game that has score_c is None or 0, EXCEPT if they explicitly wanted 3 teams.
            # "в три команды турнир мы катали только первую игру".
            if g.id > 1 and g.team_count > 2:
                # wait, let's just force team_count = 2 for all games where score_c is None or score_c == 0
                if g.score_c is None or g.score_c == 0:
                    g.team_count = 2
                    print(f"Set team_count=2 for Game {g.id}")

        await session.commit()

if __name__ == '__main__':
    asyncio.run(run())
