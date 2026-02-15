
from aiogram import Router, F, types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_session
from app.db.models import Vote, Signup, SignupStatus

router = Router()

@router.callback_query(F.data.startswith("vote_"))
async def process_vote(callback: types.CallbackQuery, session: AsyncSession):
    _, game_id, target_id = callback.data.split("_")
    game_id = int(game_id)
    target_id = int(target_id)
    voter_id = callback.from_user.id
    
    # Check if voter played in the game
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

    # Get Target's Team
    result = await session.execute(
        select(Signup).where(Signup.game_id == game_id, Signup.user_id == target_id)
    )
    target_signup = result.scalar_one_or_none()
    
    if not target_signup or not target_signup.team:
        await callback.answer("Ошибка: Игрок не найден или без команды.", show_alert=True)
        return

    target_team = target_signup.team

    # Check if already voted FOR THIS TEAM
    result = await session.execute(
        select(Vote).where(
            Vote.game_id == game_id, 
            Vote.voter_id == voter_id,
            Vote.vote_team == target_team
        )
    )
    if result.scalar_one_or_none():
        await callback.answer(f"Вы уже выбрали MVP команды {target_team.value}!", show_alert=True)
        return

    # Record vote
    vote = Vote(
        game_id=game_id, 
        voter_id=voter_id, 
        target_id=target_id, 
        vote_team=target_team
    )
    session.add(vote)
    await session.commit()
    
    await callback.answer(f"Голос за {target_team.value} принят! (Осталось выбрать вторую команду)")

    # Voting continues until scheduled task or manual trigger.
    # We removed early trigger here to avoid spamming the chat with results after every vote.
