import asyncio
import sys
import os
from sqlalchemy import select, desc
from app.db.database import async_session_maker
from app.db.models import User, Game, Signup, GameStats, RatingHistory, SignupStatus, GameStatus, Team
from app.config import settings

# Setup Path
sys.path.insert(0, os.getcwd())

async def debug_history(user_ident):
    async with async_session_maker() as session:
        # Find User
        res = await session.execute(select(User).where(User.full_name.ilike(f"%{user_ident}%")))
        user = res.scalars().first()
        if not user:
            print("User not found")
            return

        print(f"User: {user.full_name} ({user.user_id})")

        # Query
        query = (
            select(Game, Signup, GameStats, RatingHistory)
            .join(Signup, Game.id == Signup.game_id)
            .outerjoin(GameStats, (Game.id == GameStats.game_id) & (GameStats.user_id == user.user_id))
            .outerjoin(RatingHistory, (Game.id == RatingHistory.game_id) & (RatingHistory.user_id == user.user_id))
            .where(
                Signup.user_id == user.user_id,
                Signup.status == SignupStatus.ACTIVE,
                Game.status == GameStatus.FINISHED
            )
            .order_by(desc(Game.date_time))
            .limit(10)
        )

        result = await session.execute(query)
        matches = result.all()
        print(f"Matches found: {len(matches)}")

        for game, signup, stats, rating in matches:
            print(f"Processing Game {game.id}...")
            try:
                # Logic from profile.py
                team_icon = "⚪"
                if signup.team == Team.A: team_icon = "🟠"
                elif signup.team == Team.B: team_icon = "🟢"
                elif signup.team == Team.C: team_icon = "🔵"
                
                print(f"Team: {signup.team} -> {team_icon}")

                result_icon = "🤝" 
                if game.winner_team:
                    if game.winner_team == signup.team:
                        result_icon = "🏆" 
                    else:
                         # Bug? If signup.team is None?
                         # Assuming signup.team is not None since we show icon.
                        result_icon = "💀" 
                
                print(f"Result: {result_icon}")

                score_text = f"{game.score_a or 0}:{game.score_b or 0}"
                if game.team_count == 3:
                     score_text += f":{game.score_c or 0}"
                
                print(f"Score: {score_text}")

                date_str = game.date_time.strftime("%d.%m")
                loc_short = game.location.split('|')[0].split(',')[0].strip()
                
                print(f"Loc: {loc_short}")
                
                row = f"{result_icon} <b>{date_str} | {loc_short}</b> ({score_text})\n"
                
                details = []
                details.append(f"{team_icon} Команда")

                if stats and stats.goals > 0:
                    details.append(f"⚽ {stats.goals}")
                    
                if rating:
                    sign = "+" if rating.change > 0 else ""
                    details.append(f"📈 {sign}{rating.change} MMR")
                
                print(f"Details: {details}")

            except Exception as e:
                print(f"CRASH ON GAME {game.id}: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_history("Yernur"))
