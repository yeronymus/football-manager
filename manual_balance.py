import asyncio
from sqlalchemy import select
from app.db.database import get_session
from app.db.models import Game, Signup, User, SignupStatus, Team, Position
from app.bot.balancer import balance_teams, Player

async def manual_balance():
    async for session in get_session():
        # 1. Find latest active game
        result = await session.execute(
            select(Game)
            .order_by(Game.date_time.desc())
            .limit(1)
        )
        game = result.scalar_one_or_none()
        
        if not game:
            print("No games found.")
            return

        print(f"Balancing Game: {game.id} at {game.location} ({game.date_time})")

        # 2. Get active players
        result = await session.execute(
            select(User)
            .join(Signup)
            .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
        )
        players = result.scalars().all()
        
        if not players:
            print("No active players.")
            return

        print(f"Active Players: {len(players)}")

        # 3. Balance
        wrapped_players = []
        for p in players:
            # We need to fetch their signup to check for position override?
            # Balancer uses User position mainly.
            # Let's verify if signup has override.
            s_res = await session.execute(select(Signup).where(Signup.game_id == game.id, Signup.user_id == p.user_id))
            signup = s_res.scalar_one()
            
            # Helper to patch user object temporarily if needed, or update Player class
            # The Player class in balancer.py reads user.player_position.
            if signup.position:
                p.player_position = signup.position # Temp override for balancer
            
            wrapped_players.append(Player(p))
            
        teams = balance_teams(wrapped_players, team_count=game.team_count)
        
        # 4. Save to DB
        team_map = {0: Team.A, 1: Team.B, 2: Team.C}
        
        print("\n--- RESULTS ---")
        for i, team_players in enumerate(teams):
            t_enum = team_map.get(i)
            print(f"\nTeam {t_enum.value}:")
            for p in team_players:
                print(f"- {p.name} ({p.position})")
                
                # Update DB
                s_res = await session.execute(select(Signup).where(Signup.game_id == game.id, Signup.user_id == p.id))
                signup = s_res.scalar_one()
                signup.team = t_enum
                
        await session.commit()
        print("\nUpdates saved to Database!")

if __name__ == "__main__":
    try:
        asyncio.run(manual_balance())
    except Exception as e:
        with open("manual_balance_error.log", "w") as f:
            import traceback
            f.write(traceback.format_exc())
        print(f"Error: {e}")
