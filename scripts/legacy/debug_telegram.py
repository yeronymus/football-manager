import asyncio
import sys
import os
import traceback

# Ensure app is in path
sys.path.append(os.getcwd())
sys.path.append("/app")

async def main():
    try:
        from app.config import settings
        from app.db.database import init_models, get_session_maker
        from app.db.models import Game, Signup, User, SignupStatus
        from sqlalchemy import select
        from app.bot.main import bot

        await init_models()
        
        session_maker = get_session_maker()
        async with session_maker() as session:
            game_id = 5
            report = f"DEBUG REPORT for Game #{game_id}\n"
            
            # Check Game
            result = await session.execute(select(Game).where(Game.id == game_id))
            game = result.scalar_one_or_none()
            
            if game:
                report += f"Game Found: ID={game.id}\nStatus={game.status}\nChatID={game.chat_id}\nDuration={game.duration}\n"
            else:
                 report += "Game NOT FOUND!\n"

            # Check Signups
            result = await session.execute(
                select(Signup).where(Signup.game_id == game_id)
            )
            signups = result.scalars().all()
            active = [s for s in signups if s.status == SignupStatus.ACTIVE]
            report += f"Total Signups: {len(signups)}\nActive Signups: {len(active)}\n"
            
            # Helper to send
            admin_id = settings.admin_ids[0] if settings.admin_ids else settings.system_owner_id
            if admin_id:
                print(f"Sending report to Admin: {admin_id}")
                try:
                    await bot.send_message(chat_id=admin_id, text=report)
                    print("Report sent!")
                except Exception as e:
                    print(f"Failed to send to admin: {e}")
                    # Try sending to game chat if admin fails
                    if game and game.chat_id:
                         await bot.send_message(chat_id=game.chat_id, text=report)
            else:
                print("No Admin ID found.")
                
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
    finally:
        if 'bot' in locals():
            await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
