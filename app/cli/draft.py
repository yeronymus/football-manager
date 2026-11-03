from typing import Optional

from sqlalchemy import func, select

from app.db.database import async_session_maker
from app.db.models import Game, GameStats, GameStatus, PlayerProfile, Signup, SignupStatus, User


def calc_win_pct(w: int, d: int, l: int) -> str:
    total = w + l + d
    if total == 0:
        return "-"
    return f"{w / total * 100:.0f}%"


async def generate_draft_report_command(args) -> None:
    """Generate a Markdown player draft report from live database records."""
    output_file = getattr(args, "output", None) or "Draft_Stats.md"
    chat_id: Optional[int] = getattr(args, "chat_id", None)
    print(f"Generating Draft Report to {output_file}...")

    async with async_session_maker() as db:
        if chat_id is not None:
            stmt = (
                select(User, PlayerProfile)
                .join(PlayerProfile, PlayerProfile.user_id == User.user_id)
                .where(PlayerProfile.chat_id == chat_id)
            )
            rows = (await db.execute(stmt)).all()
            players = [
                (
                    u.user_id,
                    u.full_name or f"Player #{u.user_id}",
                    u.player_position.value if u.player_position else "-",
                    p.rating or 100,
                    p.games_played or 0,
                    p.stats_mvp or 0,
                )
                for u, p in rows
            ]
        else:
            users = (await db.execute(select(User))).scalars().all()
            players = [
                (
                    u.user_id,
                    u.full_name or f"Player #{u.user_id}",
                    u.player_position.value if u.player_position else "-",
                    u.rating or 100,
                    u.games_played or 0,
                    u.stats_mvp or 0,
                )
                for u in users
            ]

        goals_stmt = select(GameStats.user_id, func.coalesce(func.sum(GameStats.goals), 0))
        if chat_id is not None:
            goals_stmt = goals_stmt.join(Game, Game.id == GameStats.game_id).where(Game.chat_id == chat_id)
        goals_stmt = goals_stmt.group_by(GameStats.user_id)
        goals_map = {uid: int(total) for uid, total in (await db.execute(goals_stmt)).all()}

        wdl_map: dict[int, list[int]] = {}
        signup_stmt = (
            select(Signup.user_id, Signup.team, Game.winner_team)
            .join(Game, Game.id == Signup.game_id)
            .where(Signup.status == SignupStatus.ACTIVE, Game.status == GameStatus.FINISHED)
        )
        if chat_id is not None:
            signup_stmt = signup_stmt.where(Game.chat_id == chat_id)

        for uid, team, winner_team in (await db.execute(signup_stmt)).all():
            counts = wdl_map.setdefault(uid, [0, 0, 0])  # [wins, draws, losses]
            if winner_team is None:
                counts[1] += 1
            elif team is not None and team == winner_team:
                counts[0] += 1
            elif team is not None:
                counts[2] += 1

    draft_rows = []
    for uid, name, pos, elo, gp, mvp in players:
        w, d, l = wdl_map.get(uid, [0, 0, 0])
        goals = goals_map.get(uid, 0)
        draft_rows.append((name, pos, elo, gp, goals, calc_win_pct(w, d, l), mvp))

    draft_rows.sort(key=lambda item: (-item[2], -item[4], -item[3], item[0]))

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("| Player | Pos | ELO | Games | Goals | Win% | MVP |\n")
        f.write("|--------|-----|-----|-------|-------|------|-----|\n")
        for name, pos, elo, gp, goals, win_pct, mvp in draft_rows:
            mvp_star = f"⭐{mvp}" if mvp > 0 else ""
            f.write(f"| {name} | {pos} | **{elo}** | {gp} | {goals} | {win_pct} | {mvp_star} |\n")

    print(f"DRAFT REPORT DONE: {output_file} ({len(draft_rows)} players)")
