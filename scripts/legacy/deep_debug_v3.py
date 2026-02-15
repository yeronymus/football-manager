import asyncio
import sys
import os
import traceback

# Ensure app is in path
sys.path.append(os.getcwd())
sys.path.append("/app")

async def main():
    print("--- START ROBUST DEBUG V3 ---")
    try:
        print("Importing config...")
        try:
            from app.config import settings
            print(f"Config loaded. Bot Token: {settings.bot_token[:5]}...")
        except Exception as e:
            print(f"Config Import Failed: {e}")
            traceback.print_exc()
            return

        print("Importing DB...")
        try:
            from app.db.database import init_models, async_session_maker
            from app.db.models import Game, Signup, User, SignupStatus
            from sqlalchemy import select
            print("DB Imports OK.")
        except Exception as e:
            print(f"DB Import Failed: {e}")
            traceback.print_exc()
            return

        # await init_models() # model init might not be needed if DB exists, but safe to call
        
        async with async_session_maker() as session:
            game_id = 5
            print(f"Checking Game #{game_id}")
            
            result = await session.execute(select(Game).where(Game.id == game_id))
            game = result.scalar_one_or_none()
            
            if not game:
                print(f"ERROR: Game #{game_id} NOT FOUND in DB.")
                # print last 5 games
                print("Last 5 games:")
                result = await session.execute(select(Game).order_by(Game.id.desc()).limit(5))
                games = result.scalars().all()
                for g in games:
                    print(f" - ID: {g.id}, Status: {g.status}")
                return
            
            print(f"Game Found: ID={game.id}, Status={game.status}, ChatID={game.chat_id}")
            
            # Check Players
            result = await session.execute(
                select(Signup)
                .where(Signup.game_id == game_id)
            )
            signups = result.scalars().all()
            active_signups = [s for s in signups if s.status == SignupStatus.ACTIVE]
            print(f"Active Signups: {len(active_signups)}")
            
            if not active_signups:
                print("ERROR: No active players found!")
                # Proceed anyway to test bot connection? No, voting needs players usually.
            
            print("Importing Bot...")
            try:
                from app.bot.main import bot
                from app.scheduler.tasks import send_voting_message
                print("Bot Imports OK.")
            except Exception as e:
                print(f"Bot Import Failed: {e}")
                traceback.print_exc()
                return

            print("Attempting send_voting_message...")
            try:
                await send_voting_message(game_id)
                print("send_voting_message executed successfully.")
            except Exception as e:
                print(f"send_voting_message FAILED: {e}")
                traceback.print_exc()
            finally:
                if 'bot' in locals():
                    await bot.session.close()

    except Exception as e:
         print(f"Fatal error in main: {e}")
         traceback.print_exc()

    print("--- END ROBUST DEBUG V3 ---")

if __name__ == "__main__":
    asyncio.run(main())
