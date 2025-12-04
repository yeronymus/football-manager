from aiogram import Router, F, types
from sqlalchemy import select
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

    # Check if already voted
    result = await session.execute(select(Vote).where(Vote.game_id == game_id, Vote.voter_id == voter_id))
    if result.scalar_one_or_none():
        await callback.answer("Вы уже проголосовали!", show_alert=True)
        return

    # Record vote
    vote = Vote(game_id=game_id, voter_id=voter_id, target_id=target_id)
    session.add(vote)
    await session.commit()
    
    await callback.answer("Ваш голос учтен!")
