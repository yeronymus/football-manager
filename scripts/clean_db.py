import asyncio
import logging
import re
from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import Game

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def clean_location(loc: str) -> str:
    """Strip URLs from location string."""
    if not loc:
        return loc
    return re.sub(r'\(?https?://[^\s)]+\)?', '', loc).strip()

async def clean_database():
    """
    Standardized cleanup script to clean up DB artifacts:
    1. Removes any URL formatting or links embedded in the location fields of games.
    2. Resets team counts from 3 to 2 for games that only have score A and B (score_c is None or 0)
       and have max_players <= 14 (which indicates a 2-team setup).
    """
    logger.info("Starting database cleanup...")
    async with async_session_maker() as session:
        res = await session.execute(select(Game))
        games = res.scalars().all()
        
        locations_cleaned = 0
        team_counts_reset = 0
        
        for g in games:
            # 1. Clean location
            cleaned_loc = clean_location(g.location)
            if cleaned_loc != g.location:
                logger.info(f"Cleaned location for Game {g.id}: '{g.location}' -> '{cleaned_loc}'")
                g.location = cleaned_loc
                locations_cleaned += 1

            # 2. Reset team_count from 3 to 2 if appropriate
            # If max_players <= 14, it cannot support 3 teams (minimum 15 players for 3 teams of 5).
            # Also ensure that there's no score for the C team (score_c is 0 or None).
            if g.team_count > 2 and (g.score_c is None or g.score_c == 0) and g.max_players <= 14:
                logger.info(f"Resetting team_count for Game {g.id} from {g.team_count} to 2 (max_players: {g.max_players}, score_c: {g.score_c})")
                g.team_count = 2
                team_counts_reset += 1

        if locations_cleaned > 0 or team_counts_reset > 0:
            await session.commit()
            logger.info(f"Database updates committed. Cleaned locations: {locations_cleaned}, Reset team counts: {team_counts_reset}")
        else:
            logger.info("No cleanup actions were needed.")

if __name__ == '__main__':
    asyncio.run(clean_database())
