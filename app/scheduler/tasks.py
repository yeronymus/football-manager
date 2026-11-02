import asyncio
import logging
from sqlalchemy import select, func
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.bot.instance import bot
from app.bot.i18n import t
from app.config import settings
from app.db.database import async_session_maker
from app.db.models import Game, Signup, User, SignupStatus, GameStatus, Team

logger = logging.getLogger(__name__)


async def send_voting_message(game_id: int):
    """
    Sends the MVP voting message with inline player buttons to the chat.
    Triggered when a game duration is over or manually by admin.
    Also schedules automatic MVP calculation 24 hours after start.
    """
    async with async_session_maker() as session:
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()

        if not game:
            return

        # Get active players with team info
        result = await session.execute(
            select(User, Signup.team)
            .join(Signup)
            .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
        )
        players_data = result.all()

        if not players_data:
            return

        team_a = []
        team_b = []
        team_c = []
        unassigned = []

        for user, team in players_data:
            if team == Team.A:
                team_a.append(user)
            elif team == Team.B:
                team_b.append(user)
            elif team == Team.C:
                team_c.append(user)
            else:
                unassigned.append(user)

        # Determine chat language
        from app.bot.utils import resolve_chat_language

        chat_lang = await resolve_chat_language(session, game.chat_id)

        # Create inline keyboard with players
        from app.bot.keyboards import get_voting_keyboard, get_channel_voting_keyboard

        keyboard = get_voting_keyboard(
            game_id, team_a, team_b, team_c=team_c, unassigned=unassigned, lang=chat_lang
        )

        # Delete old voting message if it exists
        if game.voting_message_id:
            try:
                await bot.delete_message(chat_id=game.chat_id, message_id=game.voting_message_id)
            except Exception as e:
                logger.warning(f"Failed to delete old voting message for game {game_id}: {e}")

        from app.bot.utils import get_group_game_number

        game_num = await get_group_game_number(session, game)
        text = t("voting_opened_title", locale=chat_lang, game_num=game_num)

        msg = None
        try:
            msg = await bot.send_message(
                chat_id=game.chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(
                f"Failed to send standard voting keyboard: {e}, falling back to deep link keyboard"
            )
            try:
                channel_kb = get_channel_voting_keyboard(game_id, lang=chat_lang)
                msg = await bot.send_message(
                    chat_id=game.chat_id,
                    text=text,
                    reply_markup=channel_kb,
                    parse_mode="HTML",
                )
            except Exception as ex:
                logger.error(f"Failed to send fallback voting message for game {game_id}: {ex}")
                return

        if msg:
            game.voting_message_id = msg.message_id
            await session.commit()

        # Schedule automatic MVP calculation 24 hours from now
        from app.infrastructure.scheduler.service import SchedulerService
        from datetime import datetime, timedelta
        import zoneinfo

        try:
            tz = zoneinfo.ZoneInfo("Europe/Prague")
            now_dt = datetime.now(tz)
        except Exception:
            now_dt = datetime.now()

        SchedulerService().schedule_mvp_calculation_at(game_id, now_dt + timedelta(hours=24))


def format_votes_count(count: int, lang: str) -> str:
    lang = (lang or "en").lower()
    if lang == "ru":
        c_abs = abs(count)
        if c_abs % 10 == 1 and c_abs % 100 != 11:
            return f"{count} голос"
        elif 2 <= c_abs % 10 <= 4 and not (12 <= c_abs % 100 <= 14):
            return f"{count} голоса"
        else:
            return f"{count} голосов"
    return f"{count} vote" if count == 1 else f"{count} votes"


async def calculate_mvp(game_id: int):
    """
    Closes the MVP voting by removing the keyboard, determines MVP winners per team,
    announces results to the group chat, and applies MVP stats/ratings if the match is finished.
    """
    async with async_session_maker() as session:
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()

        if not game:
            return

        from app.bot.utils import get_group_game_number, resolve_chat_language

        chat_lang = await resolve_chat_language(session, game.chat_id)
        game_num = await get_group_game_number(session, game)

        # 1. Close old voting message (remove keyboard)
        if game.voting_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=game.chat_id,
                    message_id=game.voting_message_id,
                    text=t("voting_closed_title", locale=chat_lang, game_num=game_num),
                    reply_markup=None,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Failed to edit/close voting message for game {game_id}: {e}")

        # 2. Query active players and their teams
        signups_res = await session.execute(
            select(Signup.user_id, Signup.team)
            .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
        )
        active_signups = signups_res.all()
        teams_in_game = [Team.A, Team.B]
        if any(s[1] == Team.C for s in active_signups):
            teams_in_game.append(Team.C)

        # 3. Query all votes
        from app.db.models import Vote

        votes_res = await session.execute(
            select(Vote.vote_team, Vote.target_id, func.count(Vote.id))
            .where(Vote.game_id == game_id)
            .group_by(Vote.vote_team, Vote.target_id)
        )
        votes_by_team = {Team.A: {}, Team.B: {}, Team.C: {}}
        for v_team, target_id, count in votes_res.all():
            if v_team in votes_by_team:
                votes_by_team[v_team][target_id] = count

        # 4. Resolve MVPs and runners-up per team
        mvp_ids_by_team = {}
        runners_up_by_team = {}
        all_mvp_ids = set()

        for team in teams_in_game:
            team_votes = votes_by_team.get(team, {})
            if not team_votes:
                mvp_ids_by_team[team] = []
                runners_up_by_team[team] = []
                continue
            sorted_candidates = sorted(team_votes.items(), key=lambda x: x[1], reverse=True)
            max_v = sorted_candidates[0][1] if sorted_candidates else 0
            if max_v > 0:
                top_players = [uid for uid, c in sorted_candidates if c == max_v]
                mvp_ids_by_team[team] = [(uid, max_v) for uid in top_players]
                for uid in top_players:
                    all_mvp_ids.add(uid)
                runners = [(uid, c) for uid, c in sorted_candidates if c < max_v and c > 0]
                runners_up_by_team[team] = runners
            else:
                mvp_ids_by_team[team] = []
                runners_up_by_team[team] = []

        # 5. Fetch names of players
        all_candidate_ids = (
            {uid for team_list in mvp_ids_by_team.values() for uid, _ in team_list}
            | {uid for r_list in runners_up_by_team.values() for uid, _ in r_list}
        )
        user_names = {}
        if all_candidate_ids:
            u_res = await session.execute(
                select(User.user_id, User.full_name).where(User.user_id.in_(all_candidate_ids))
            )
            user_names = {row[0]: row[1] for row in u_res.all()}

        # 6. Build Announcement text
        announcement = t("mvp_results_announcement_header", locale=chat_lang, game_num=game_num)
        for team in teams_in_game:
            team_label = t(
                "team_a_name"
                if team == Team.A
                else ("team_b_name" if team == Team.B else "team_c_name"),
                locale=chat_lang,
            )
            winners = mvp_ids_by_team.get(team, [])
            runners = runners_up_by_team.get(team, [])
            if winners:
                names = ", ".join([user_names.get(uid, f"User {uid}") for uid, _ in winners])
                votes_count = winners[0][1]
                votes_display = format_votes_count(votes_count, chat_lang)
                announcement += (
                    t(
                        "mvp_team_winner_line",
                        locale=chat_lang,
                        team=team_label,
                        names=names,
                        votes=votes_count,
                        votes_display=votes_display,
                    )
                    + "\n"
                )
                for r_uid, r_votes in runners:
                    r_name = user_names.get(r_uid, f"User {r_uid}")
                    r_votes_display = format_votes_count(r_votes, chat_lang)
                    announcement += (
                        t(
                            "mvp_team_runner_up_line",
                            locale=chat_lang,
                            name=r_name,
                            votes=r_votes_display,
                        )
                        + "\n"
                    )
            else:
                announcement += t("mvp_team_none_line", locale=chat_lang, team=team_label) + "\n"

        if all_mvp_ids:
            announcement += t("mvp_results_footer", locale=chat_lang)

        # Send announcement to group chat
        try:
            await bot.send_message(
                chat_id=game.chat_id,
                text=announcement,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to send MVP announcement for game {game_id}: {e}")

        # 7. If game is already FINISHED, apply stats and ratings to the MVPs
        if game.status == GameStatus.FINISHED and all_mvp_ids:
            from app.db.models import GameStats, PlayerProfile, RatingHistory

            for mvp_id in all_mvp_ids:
                stat_res = await session.execute(
                    select(GameStats).where(
                        GameStats.game_id == game_id, GameStats.user_id == mvp_id
                    )
                )
                stat = stat_res.scalar_one_or_none()
                if stat:
                    stat.is_mvp = True
                else:
                    session.add(
                        GameStats(game_id=game_id, user_id=mvp_id, goals=0, is_mvp=True)
                    )

                u = await session.get(User, mvp_id)
                if u:
                    u.stats_mvp = (u.stats_mvp or 0) + 1
                    u.rating = (u.rating or 100) + 5

                p_res = await session.execute(
                    select(PlayerProfile).where(
                        PlayerProfile.user_id == mvp_id, PlayerProfile.chat_id == game.chat_id
                    )
                )
                p = p_res.scalar_one_or_none()
                if p:
                    p.stats_mvp = (p.stats_mvp or 0) + 1
                    p.rating = (p.rating or 100) + 5

                h_res = await session.execute(
                    select(RatingHistory).where(
                        RatingHistory.game_id == game_id, RatingHistory.user_id == mvp_id
                    )
                )
                h = h_res.scalar_one_or_none()
                if h:
                    h.new_rating = (h.new_rating or 100) + 5
                    h.change = (h.change or 0) + 5

            await session.commit()
            logger.info(f"Awarded MVP bonuses for game {game_id} to {all_mvp_ids}")


async def release_gk_slots(game_id: int):
    """
    Called after gk_hours after game creation.
    Releases the 'GK Reservation' by promoting players from the waiting list
    if empty slots remain. Silently updates the match card without private message spam.
    """
    async with async_session_maker() as session:
        game = await session.get(Game, game_id)
        if not game or game.status not in [GameStatus.OPEN, GameStatus.ACTIVE]:
            return

        result = await session.execute(
            select(func.count(Signup.id))
            .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
        )
        active_count = result.scalar()

        slots_available = game.max_players - active_count

        if slots_available > 0:
            reserves_result = await session.execute(
                select(Signup)
                .where(
                    Signup.game_id == game_id,
                    Signup.status == SignupStatus.RESERVE,
                    Signup.user_id >= 0,
                )
                .order_by(Signup.created_at)
                .limit(slots_available)
            )
            promoted_signups = reserves_result.scalars().all()

            if promoted_signups:
                for signup in promoted_signups:
                    signup.status = SignupStatus.ACTIVE

                await session.commit()

                # Update Match Card in Chat
                from app.bot.utils import format_game_message, resolve_chat_language

                chat_lang = await resolve_chat_language(session, game.chat_id)
                text = await format_game_message(game, session, lang=chat_lang)

                if game.message_id and game.chat_id:
                    from app.bot.keyboards import get_channel_game_keyboard

                    kb = get_channel_game_keyboard(game.id, lang=chat_lang)
                    try:
                        await bot.edit_message_text(
                            chat_id=game.chat_id,
                            message_id=game.message_id,
                            text=text,
                            reply_markup=kb,
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

                try:
                    from app.bot.admin_dashboard import update_dashboard_message

                    await update_dashboard_message(bot, game.id, session)
                except Exception as e:
                    logger.warning(f"Failed to update dashboard: {e}")


async def publish_game_task(game_id: int):
    """
    Publishes a scheduled game to its respective channels and group chats.
    """
    async with async_session_maker() as session:
        game = await session.get(Game, game_id)
        if not game:
            return

        from app.bot.utils import format_game_message, resolve_chat_language
        from app.bot.keyboards import get_channel_game_keyboard

        chat_lang = await resolve_chat_language(session, game.chat_id)

        # 1. Publish to Channel (Full)
        if game.channel_id:
            text_full = await format_game_message(game, session, is_short=False, lang=chat_lang)

            bot_username = settings.bot_username
            hidden_link = f'<a href="https://t.me/{bot_username}?start=game_{game.id}">&#8203;</a>'
            text_full = hidden_link + text_full

            try:
                sent_full = await bot.send_message(
                    chat_id=game.channel_id,
                    text=text_full,
                    reply_markup=get_channel_game_keyboard(game.id, lang=chat_lang),
                )
                game.channel_message_id = sent_full.message_id
            except Exception as e:
                logger.error(f"Failed to publish to channel {game.channel_id}: {e}")

        # 2. Publish to Group
        text_short = await format_game_message(game, session, is_short=False, lang=chat_lang)
        kb = get_channel_game_keyboard(game.id, lang=chat_lang)
        try:
            sent_message = await bot.send_message(
                chat_id=game.chat_id,
                text=text_short,
                reply_markup=kb,
            )

            game.message_id = sent_message.message_id
            await session.commit()

            try:
                await bot.pin_chat_message(
                    chat_id=game.chat_id, message_id=sent_message.message_id
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Failed to publish game task {game.id} to chat: {e}")
