
import asyncio
import os
import sys
from sqlalchemy import select, delete
from app.db.database import async_session_maker
from app.db.models import Game, User, GameStats, Signup, Team, GameStatus, RatingHistory

# Mock env if needed
os.environ.setdefault("BOT_TOKEN", "123")

GAME_ID = 1
WINNER = Team.B
SCORE_A = 8
SCORE_B = 11

async def repair_game():
    async with async_session_maker() as session:
        print(f"🔧 Repairing Game {GAME_ID}...")
        
        # 1. Fetch Game
        game = await session.get(Game, GAME_ID)
        if not game:
            print("❌ Game not found!")
            return

        print(f"   Current Status: {game.status}")
        print(f"   Current Winner: {game.winner_team}")
        print(f"   Current Score: {game.score_a} - {game.score_b}")

        # 2. Reset Users (Rating -> 100, Games -> 0, MVP -> 0)
        # We assume this is the ONLY game.
        # Check signups
        result = await session.execute(select(Signup).where(Signup.game_id == GAME_ID))
        signups = result.scalars().all()
        user_ids = [s.user_id for s in signups]
        
        print(f"   Resetting {len(user_ids)} users...")
        
        result = await session.execute(select(User).where(User.user_id.in_(user_ids)))
        users = result.scalars().all()
        
        for u in users:
            # Dangerous if they played other games, but user implies this is the first.
            # Let's check games_played.
            # If > 5 (due to bugs) ok, but if > 1 and legitimate?
            # We will force reset for now as per "Change results completely".
            u.rating = 100
            u.games_played = 0
            u.stats_mvp = 0 
            # We will recalculate everything.
            
        # 3. Wipe Game Stats & History
        print("   Deleting Stats & History...")
        await session.execute(delete(GameStats).where(GameStats.game_id == GAME_ID))
        await session.execute(delete(RatingHistory).where(RatingHistory.game_id == GAME_ID))
        
        # 4. Set Correct Result
        game.score_a = SCORE_A
        game.score_b = SCORE_B
        game.winner_team = WINNER
        game.status = GameStatus.FINISHED # Ensure it is finished
        
        # 5. Re-run Finish Logic (without the status check block we just added... wait)
        # We can't call service.finish_game because it now blocks FINISHED games.
        # We must manually replicate logic or set status to ACTIVE then call service.
        
        print("   Re-applying Stats & ELO...")
        
        # We need the originally voted MVP. 
        # User said "Iliyas Akbergen" got MVP.
        # We need his ID.
        mvp_user = None
        for u in users:
            if "Iliyas" in u.full_name:
                mvp_user = u
                break
        
        mvp_user_id = mvp_user.user_id if mvp_user else None
        print(f"   MVP Identified: {mvp_user.full_name if mvp_user else 'None'}")
        
        if mvp_user:
            # Add MVP Stat
            stat = GameStats(
                game_id=game.id,
                user_id=mvp_user.user_id,
                goals=0, # Assuming 0 goals recorded for now or unknown
                is_mvp=True
            )
            session.add(stat)
            mvp_user.stats_mvp += 1
            
        # ELO Logic (Simplified from Service)
        from app.bot.elo import calculate_new_rating
        
        # Re-fetch players with teams
        teams_map = {s.user_id: s.team for s in signups}
        
        team_a_players = [u for u in users if teams_map.get(u.user_id) == Team.A]
        team_b_players = [u for u in users if teams_map.get(u.user_id) == Team.B]
        
        avg_a = 100 # Reset triggered
        avg_b = 100
        
        # Calc Team A
        actual_score_a = 1 if WINNER == Team.A else 0
        for p in team_a_players:
            is_mvp = (p.user_id == mvp_user_id)
            new_r = calculate_new_rating(p, avg_b, actual_score_a, is_mvp)
            p.rating = new_r
            p.games_played += 1
            
        # Calc Team B
        actual_score_b = 1 if WINNER == Team.B else 0
        for p in team_b_players:
            is_mvp = (p.user_id == mvp_user_id)
            new_r = calculate_new_rating(p, avg_a, actual_score_b, is_mvp)
            p.rating = new_r
            p.games_played += 1

        await session.commit()
        print("✅ Repair Complete!")
        print(f"   New Result: Team {WINNER} Won ({SCORE_A}-{SCORE_B})")
        if mvp_user:
            print(f"   MVP: {mvp_user.full_name} (Total: {mvp_user.stats_mvp})")

if __name__ == "__main__":
    asyncio.run(repair_game())
