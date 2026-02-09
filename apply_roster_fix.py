import asyncio
import os
import sys
from sqlalchemy import select, func, distinct
from app.db.database import async_session_maker
from app.db.models import Game, Signup, User, Team, SignupStatus
from app.bot.main import bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

# --- THE VOTE HANDLER CODE WITH CHECKMARKS AND FIX ---
VOTE_HANDLER_CODE = r'''
from aiogram import Router, F, types
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_session
from app.db.models import Vote, Signup, SignupStatus, Team, User, Game
import logging

# Configure File Logging for Debugging
logging.basicConfig(
    filename='/app/vote_debug.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

router = Router()

@router.callback_query(F.data.startswith("vote_"))
async def process_vote(callback: types.CallbackQuery, session: AsyncSession):
    try:
        logger.info(f"Vote attempt by {callback.from_user.id} data={callback.data}")
        
        # Parse Data
        parts = callback.data.split("_")
        if len(parts) != 3:
            logger.error("Invalid data format")
            await callback.answer("Error: Invalid data format", show_alert=True)
            return
            
        _, game_id, target_id = parts
        game_id = int(game_id)
        target_id = int(target_id)
        voter_id = callback.from_user.id
        
        # 1. Validate Voter (Participants only)
        result = await session.execute(
            select(Signup).where(
                Signup.game_id == game_id, 
                Signup.user_id == voter_id, 
                Signup.status == SignupStatus.ACTIVE
            )
        )
        if not result.scalar_one_or_none():
            await callback.answer("Голосовать могут только участники матча!", show_alert=True)
            return

        # 2. Get Target info
        result = await session.execute(
            select(Signup).where(Signup.game_id == game_id, Signup.user_id == target_id)
        )
        target_signup = result.scalar_one_or_none()
        
        if not target_signup or not target_signup.team:
            await callback.answer("Ошибка: Игрок не найден.", show_alert=True)
            return

        target_team = target_signup.team

        # 3. Check Duplicate Vote (One per team)
        result = await session.execute(
            select(Vote).where(
                Vote.game_id == game_id, 
                Vote.voter_id == voter_id, 
                Vote.vote_team == target_team
            )
        )
        existing_vote = result.scalar_one_or_none()
        
        if existing_vote:
            if existing_vote.target_id == target_id:
                await callback.answer(f"Вы уже выбрали этого игрока!", show_alert=True)
                return
            else:
                await callback.answer(f"Вы уже выбрали MVP команды {target_team.value}!", show_alert=True)
                return

        # 4. Record Vote
        vote = Vote(
            game_id=game_id, 
            voter_id=voter_id, 
            target_id=target_id, 
            vote_team=target_team
        )
        session.add(vote)
        await session.commit()
        
        logger.info(f"Vote recorded: {voter_id} -> {target_id} ({target_team})")
        await callback.answer(f"✅ Голос за {target_team.value} принят!")
        
        # 5. UI Update (Skipped for public anonymity)
        pass

        # 6. Check Completion (FIXED LOGIC)
        try:
            # Count Active Players
            res = await session.execute(
                select(func.count(Signup.id)).where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
            )
            total_players = res.scalar() or 0
            
            # Count UNIQUE Voters (Distinct IDs)
            res = await session.execute(
                select(func.count(distinct(Vote.voter_id))).where(Vote.game_id == game_id)
            )
            unique_voters = res.scalar() or 0
            
            logger.info(f"Stats: {unique_voters}/{total_players} unique voters.")
            
            if unique_voters >= total_players:
                try:
                    from app.scheduler.tasks import calculate_mvp
                    await calculate_mvp(game_id)
                except ImportError:
                     pass 
        except Exception as e:
            logger.error(f"Post-vote stats error: {e}")

    except Exception as e:
        logger.error(f"CRITICAL VOTE ERROR: {e}", exc_info=True)
'''

async def patch_handler():
    print("PATCHING handler file with COUNT DISTINT FIX...")
    path = "/app/app/bot/vote_handlers.py"
    try:
        with open(path, "w") as f:
            f.write(VOTE_HANDLER_CODE)
        print(f"Successfully wrote {path}")
    except Exception as e:
        print(f"Failed to write file: {e}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "patch"
    if mode == "patch":
        asyncio.run(patch_handler())
    else:
        print("Usage: python3 script.py patch")
