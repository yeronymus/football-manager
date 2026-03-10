#!/usr/bin/env python3
"""
Dry-run + Recalculate all ratings from scratch.
Run inside Docker: docker compose exec app python3 scripts/recalculate_prod.py dry
"""
import asyncio
from sqlalchemy import select, delete, text
from app.db.models import User, Game, Signup, SignupStatus, Team, GameStats, GameStatus, RatingHistory
from app.db.database import async_session_maker as AsyncSessionLocal

async def dry_run():
    async with AsyncSessionLocal() as s:
        print("=" * 70)
        print("📊 DRY RUN — Checking DB State")
        print("=" * 70)

        res = await s.execute(
            select(Game).where(Game.status == GameStatus.FINISHED).order_by(Game.date_time.asc())
        )
        games = res.scalars().all()
        print(f"\n✅ Found {len(games)} finished games:\n")
        print(f"{'ID':<5} {'Date':<12} {'Score A':<9} {'Score B':<9} {'Score C':<9} {'Winner':<8} {'Teams':<6} {'Players':<9} {'MVPs'}")
        print("-" * 75)
        for g in games:
            p_res = await s.execute(
                select(Signup).where(Signup.game_id == g.id, Signup.status == SignupStatus.ACTIVE)
            )
            players = p_res.scalars().all()
            mvp_res = await s.execute(
                select(GameStats).where(GameStats.game_id == g.id, GameStats.is_mvp == True)
            )
            mvps = mvp_res.scalars().all()
            mvp_ids = [m.user_id for m in mvps]

            # Get mvp names
            mvp_names = []
            for mid in mvp_ids:
                u = await s.get(User, mid)
                if u: mvp_names.append(u.full_name.split()[0])

            date_str = g.date_time.strftime('%d.%m.%Y')
            sc = g.score_c if g.score_c is not None else '-'
            win = g.winner_team.value if g.winner_team else 'DRAW'
            print(f"#{g.id:<4} {date_str:<12} {str(g.score_a)+'g':<9} {str(g.score_b)+'g':<9} {str(sc):<9} {win:<8} {g.team_count:<6} {len(players):<9} {', '.join(mvp_names) or '—'}")

        print("\n📋 Current Ratings (Top 15):\n")
        ur = await s.execute(select(User).order_by(User.rating.desc()).limit(15))
        users = ur.scalars().all()
        print(f"{'Name':<28} {'Rating':<8} {'Games':<7}")
        print("-" * 45)
        for u in users:
            print(f"{u.full_name:<28} {u.rating:<8} {u.games_played}")

        return len(games)

async def recalculate():
    async with AsyncSessionLocal() as s:
        print("\n" + "=" * 70)
        print("🚀 RECALCULATE ALL RATINGS")
        print("=" * 70)

        # 1. Reset all users
        print("\n🔄 Resetting all users to 100 ELO, 0 games...")
        await s.execute(text("UPDATE users SET rating=100, games_played=0, stats_mvp=0, stats_matches=0"))

        # 2. Clear rating history
        print("🗑️  Clearing rating history...")
        await s.execute(delete(RatingHistory))

        # 3. Get all finished games in order
        res = await s.execute(
            select(Game).where(Game.status == GameStatus.FINISHED).order_by(Game.date_time.asc())
        )
        games = res.scalars().all()
        print(f"\n⚙️  Processing {len(games)} games...\n")

        for game in games:
            date_str = game.date_time.strftime('%d.%m.%Y')
            print(f"  Game #{game.id} ({date_str}) {game.score_a}:{game.score_b}" +
                  (f":{game.score_c}" if game.score_c is not None else "") +
                  f" — Winner: {game.winner_team.value if game.winner_team else 'DRAW'}")

            # Build team_points
            team_points = {}
            if game.team_count == 2:
                sa, sb = game.score_a or 0, game.score_b or 0
                if sa == sb:
                    team_points[Team.A] = 0
                    team_points[Team.B] = 0
                elif game.winner_team == Team.A:
                    team_points[Team.A] = 10
                    team_points[Team.B] = -5
                elif game.winner_team == Team.B:
                    team_points[Team.A] = -5
                    team_points[Team.B] = 10
                else:
                    team_points[Team.A] = 10 if sa > sb else -5
                    team_points[Team.B] = 10 if sb > sa else -5
            elif game.team_count == 3:
                scores = [(Team.A, game.score_a or 0), (Team.B, game.score_b or 0), (Team.C, game.score_c or 0)]
                unique = sorted(list(set(v for _, v in scores)), reverse=True)
                for t, sc in scores:
                    if len(unique) == 1: team_points[t] = 0
                    else:
                        r = unique.index(sc)
                        team_points[t] = 10 if r == 0 else (0 if r == 1 else -5)

            # Get MVPs
            mvp_res = await s.execute(
                select(GameStats).where(GameStats.game_id == game.id, GameStats.is_mvp == True)
            )
            mvp_ids = set(m.user_id for m in mvp_res.scalars().all())

            # Get active players
            p_res = await s.execute(
                select(User, Signup.team)
                .join(Signup)
                .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
            )
            players_data = p_res.all()

            for user, team in players_data:
                old_rating = user.rating
                base = team_points.get(team, 0)
                is_mvp = user.user_id in mvp_ids
                change = base + (5 if is_mvp else 0)

                if is_mvp:
                    user.stats_mvp += 1

                user.rating += change
                user.games_played += 1
                user.stats_matches += 1

                s.add(RatingHistory(
                    user_id=user.user_id,
                    game_id=game.id,
                    old_rating=old_rating,
                    new_rating=user.rating,
                    change=change,
                ))

                print(f"    {user.full_name:<28} {old_rating} → {user.rating}  ({'+' if change>=0 else ''}{change})" + (" ⭐MVP" if is_mvp else ""))

        await s.commit()
        print("\n" + "=" * 70)
        print("✨ RECALCULATION COMPLETE!")
        print("=" * 70)

        # Final leaderboard
        print("\n🏆 NEW LEADERBOARD (Top 20):\n")
        ur = await s.execute(select(User).order_by(User.rating.desc()).limit(20))
        users = ur.scalars().all()
        print(f"{'#':<4} {'Name':<28} {'ELO':<8} {'Games':<7} {'MVP'}")
        print("-" * 55)
        for i, u in enumerate(users, 1):
            mvp_str = f"⭐{u.stats_mvp}" if u.stats_mvp else ""
            print(f"{i:<4} {u.full_name:<28} {u.rating:<8} {u.games_played:<7} {mvp_str}")

async def main(mode):
    if mode == "dry":
        print("\n🔍 DRY RUN MODE (no changes)\n")
        await dry_run()
        print("\n💡 Run with '--go' to apply changes")
    elif mode == "--go":
        await dry_run()
        print("\n⚠️  ABOUT TO WRITE CHANGES TO DB!")
        confirm = input("Type 'YES' to confirm: ").strip()
        if confirm == "YES":
            await recalculate()
        else:
            print("Cancelled.")

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry"
    asyncio.run(main(mode))
