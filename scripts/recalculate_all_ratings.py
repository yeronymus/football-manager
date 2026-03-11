import asyncio
import logging
from sqlalchemy import select, delete, text
from app.db.database import async_session_maker
from app.db.models import User, Game, Signup, SignupStatus, Team, GameStats, GameStatus, RatingHistory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def recalculate_all():
    async with async_session_maker() as session:
        print("=== 🚀 RECALCULATING ALL RATINGS 🚀 ===")
        
        # 1. Reset all users
        print("🔄 Resetting users to baseline (100 MMR)...")
        await session.execute(text("UPDATE users SET rating = 100, games_played = 0, stats_mvp = 0, stats_matches = 0"))
        
        # 2. Clear Rating History
        print("🗑️ Clearing Rating History...")
        await session.execute(delete(RatingHistory))
        
        # 3. Fetch all finished games in order
        print("🔍 Fetching finished games...")
        res = await session.execute(select(Game).where(Game.status == GameStatus.FINISHED).order_by(Game.date_time.asc()))
        games = res.scalars().all()
        
        print(f"Found {len(games)} finished games.")
        
        for game in games:
            print(f"\nProcessing Game {game.id} ({game.date_time.strftime('%d.%m.%Y')})")
            
            # Determine Ranks and Points (Fixed Logic)
            team_points = {}
            if game.team_count == 2:
                if game.score_a == game.score_b:
                    team_points[Team.A] = 0
                    team_points[Team.B] = 0
                elif game.winner_team == Team.A:
                    team_points[Team.A] = 10
                    team_points[Team.B] = -5
                elif game.winner_team == Team.B:
                    team_points[Team.A] = -5
                    team_points[Team.B] = 10
                else:
                    # Fallback
                    sa = game.score_a or 0
                    sb = game.score_b or 0
                    if sa > sb:
                        team_points[Team.A] = 10
                        team_points[Team.B] = -5
                    elif sb > sa:
                        team_points[Team.A] = -5
                        team_points[Team.B] = 10
                    else:
                        team_points[Team.A] = 0
                        team_points[Team.B] = 0
            
            elif game.team_count == 3:
                scores = [
                    (Team.A, game.score_a or 0),
                    (Team.B, game.score_b or 0),
                    (Team.C, game.score_c or 0)
                ]
                unique_scores = sorted(list(set(s[1] for s in scores)), reverse=True)
                for t, score in scores:
                    if len(unique_scores) == 1:
                        team_points[t] = 0
                    else:
                        rank = unique_scores.index(score)
                        if rank == 0: team_points[t] = 10
                        elif rank == 1: team_points[t] = 0
                        else: team_points[t] = -5
            
            # Get MVPs
            mvp_res = await session.execute(select(GameStats.user_id).where(GameStats.game_id == game.id, GameStats.is_mvp == True))
            mvp_ids = set(mvp_res.scalars().all())
            
            # Get Players
            p_res = await session.execute(
                select(User, Signup.team)
                .join(Signup)
                .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
            )
            players_data = p_res.all()
            
            for user, team in players_data:
                old_rating = user.rating
                change = team_points.get(team, 0)
                
                is_mvp = (user.user_id in mvp_ids)
                if is_mvp:
                    change += 5
                    user.stats_mvp += 1
                
                user.rating += change
                user.games_played += 1
                user.stats_matches += 1
                
                # Record History
                session.add(RatingHistory(
                    user_id=user.user_id,
                    game_id=game.id,
                    old_rating=old_rating,
                    new_rating=user.rating,
                    change=change,
                    date=game.date_time
                ))
                print(f"  {user.full_name}: {old_rating} -> {user.rating} ({'+' if change>=0 else ''}{change})")
        
        await session.commit()
        print("\n=== ✨ RECALCULATION COMPLETE ✨ ===")

if __name__ == "__main__":
    asyncio.run(recalculate_all())
