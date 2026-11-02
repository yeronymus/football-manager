from typing import Callable
from aiogram import Router, F, types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.i18n import t
from app.db.models import Vote, Signup, SignupStatus, Team

router = Router()

@router.callback_query(F.data.startswith("vote_"))
async def process_vote(
    callback: types.CallbackQuery,
    session: AsyncSession,
    _: Callable[..., str] = t,
):
    _, game_id, target_id = callback.data.split("_")
    game_id = int(game_id)
    target_id = int(target_id)
    voter_id = callback.from_user.id
    
    # 0. Check for self-voting
    if voter_id == target_id:
        await callback.answer(_("vote_cannot_self"), show_alert=True)
        return
    
    # 1. Check if voter played in the game
    result = await session.execute(
        select(Signup).where(
            Signup.game_id == game_id, 
            Signup.user_id == voter_id, 
            Signup.status == SignupStatus.ACTIVE
        )
    )
    if not result.scalar_one_or_none():
        await callback.answer(_("vote_only_participants"), show_alert=True)
        return

    # Get Target's Team
    result = await session.execute(
        select(Signup).where(Signup.game_id == game_id, Signup.user_id == target_id)
    )
    target_signup = result.scalar_one_or_none()
    
    if not target_signup:
        await callback.answer(_("vote_player_not_found"), show_alert=True)
        return

    target_team = target_signup.team
    is_general_vote = (target_team is None)
    effective_team = target_team or Team.A

    # Check if already voted FOR THIS TEAM (or general match MVP)
    result = await session.execute(
        select(Vote).where(
            Vote.game_id == game_id, 
            Vote.voter_id == voter_id,
            Vote.vote_team == effective_team
        )
    )
    if result.scalar_one_or_none():
        if is_general_vote:
            await callback.answer(_("vote_already_voted_general"), show_alert=True)
        else:
            await callback.answer(_("vote_already_voted_team", team=target_team.value), show_alert=True)
        return

    # Record vote
    vote = Vote(
        game_id=game_id, 
        voter_id=voter_id, 
        target_id=target_id, 
        vote_team=effective_team
    )
    session.add(vote)
    await session.commit()

    if is_general_vote:
        await callback.answer(_("vote_general_done"))
        return

    # Check how many teams the voter has now voted for
    voted_result = await session.execute(
        select(Vote.vote_team).where(
            Vote.game_id == game_id,
            Vote.voter_id == voter_id
        )
    )
    voted_teams = {row[0] for row in voted_result.all()}

    # Query participating teams in this game
    teams_query = await session.execute(
        select(Signup.team).where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE).distinct()
    )
    participating_teams = {row[0] for row in teams_query.all() if row[0] is not None}
    if not participating_teams:
        participating_teams = {Team.A, Team.B}

    remaining = participating_teams - voted_teams

    if not remaining:
        await callback.answer(_("vote_all_teams_done" if len(participating_teams) > 2 else "vote_both_done"))
    else:
        rem_labels = [
            _("team_a_name") if t_val == Team.A else (_("team_b_name") if t_val == Team.B else _("team_c_name"))
            for t_val in remaining
        ]
        await callback.answer(_("vote_one_done", team=target_team.value, remaining=", ".join(rem_labels)))
