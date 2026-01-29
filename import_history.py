import asyncio
import json
import logging
import os
from datetime import datetime
from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import Game, User, Signup, GameStats, SignupStatus, GameStatus, Team, Position, RatingHistory
from app.bot.elo import calculate_new_rating

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = "history_data.json"

async def import_history():
    if not os.path.exists(DATA_FILE):
        print(f"File {DATA_FILE} not found!")
        return

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    async with async_session_maker() as session:
        # 1. Process Users (Ensure they exist)
        print("Checking users...")
        for player in data.get("players", []):
            try:
                # Try fetch
                result = await session.execute(select(User).where(User.user_id == player["id"]))
                user = result.scalar_one_or_none()
                
                pos_enum = Position[player["position"]]
                
                if not user:
                    print(f"Creating user {player['name']} ({player['id']})")
                    user = User(
                        user_id=player["id"],
                        full_name=player["name"],
                        username=player.get("username"),
                        player_position=pos_enum,
                        rating=1200
                    )
                    session.add(user)
                else:
                    # Update fields if needed? User might exist from bot usage.
                    # Don't reset rating if already engaged, BUT user said "retroactive", 
                    # implies we might need to be careful not to double count if they played Game 3?
                    # Assuming we run this ONCE before they play too many games.
                    pass
            except Exception as e:
                print(f"Error processing user {player['name']}: {e}")
                
        await session.commit()

        # 2. Process Games
        print("Processing games...")
        for game_data in data.get("games", []):
            try:
                # Check if game exists (by location/date to avoid duplicates?)
                # Or just create new.
                # Let's assume we are creating NEW historic games.
                
                date_obj = datetime.strptime(game_data["date"], "%Y-%m-%d %H:%M")
                
                game = Game(
                    chat_id=game_data["chat_id"],
                    created_by=game_data["created_by_id"],
                    date_time=date_obj,
                    location=game_data["location"],
                    max_players=len(game_data["team_a"]) + len(game_data["team_b"]),
                    price=0,
                    status=GameStatus.FINISHED,
                    winner_team=Team[game_data["winner"]], # "A" or "B"
                    score_a=game_data["score_a"],
                    score_b=game_data["score_b"],
                    team_count=2
                )
                session.add(game)
                await session.flush() # Get ID
                print(f"Created Game ID {game.id} at {game.location}")

                # Signups & Stats
                # We need to calculate ELO update for this game!
                # Because it's "retroactive", we ideally should replay history?
                # The user said "Add results... to update rating".
                # If we just add them now, we simply apply ELO delta to CURRENT rating. 
                # That's acceptable for "filling in gaps".
                
                team_a_ids = game_data["team_a"]
                team_b_ids = game_data["team_b"]
                
                # Fetch user objects for ELO
                res_a = await session.execute(select(User).where(User.user_id.in_(team_a_ids)))
                users_a = res_a.scalars().all()
                
                res_b = await session.execute(select(User).where(User.user_id.in_(team_b_ids)))
                users_b = res_b.scalars().all()
                
                # Create Signups/Stats
                all_users = users_a + users_b
                for u in all_users:
                    team = Team.A if u.user_id in team_a_ids else Team.B
                    su = Signup(game_id=game.id, user_id=u.user_id, status=SignupStatus.ACTIVE, team=team)
                    session.add(su)
                    
                    # Stats (Goals/Assists if avail? Default 0)
                    st = GameStats(game_id=game.id, user_id=u.user_id, goals=0, assists=0)
                    session.add(st)
                
                # Verify we have all players
                if len(users_a) != len(team_a_ids) or len(users_b) != len(team_b_ids):
                    print(f"WARNING: Some players in Game {game.id} not found in DB!")
                    
                # Calculate ELO
                # Using existing elo.py logic
                new_ratings_a, new_ratings_b, expected_a, expected_b = calculate_new_rating(
                    [u.rating for u in users_a],
                    [u.rating for u in users_b],
                    game.score_a,
                    game.score_b
                )
                
                # Apply Ratings
                for i, u in enumerate(users_a):
                    diff = new_ratings_a[i] - u.rating
                    u.rating = new_ratings_a[i]
                    # Log
                    rh = RatingHistory(user_id=u.user_id, game_id=game.id, previous_rating=u.rating - diff, new_rating=u.rating, change=diff)
                    session.add(rh)
                    
                for i, u in enumerate(users_b):
                    diff = new_ratings_b[i] - u.rating
                    u.rating = new_ratings_b[i]
                    rh = RatingHistory(user_id=u.user_id, game_id=game.id, previous_rating=u.rating - diff, new_rating=u.rating, change=diff)
                    session.add(rh)

                print("Ratings updated.")
                
            except Exception as e:
                print(f"Failed to process game {game_data['location']}: {e}")
                
        await session.commit()
        print("Accessfully Imported History!")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(import_history())
