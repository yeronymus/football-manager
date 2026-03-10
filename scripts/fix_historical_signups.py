#!/usr/bin/env python3
"""
Fixes historical signups (Games 1-7) and recalculates all ratings.
Run: docker compose exec app python3 scripts/fix_historical_signups.py
"""
import asyncio
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
from app.db.models import User, Game, Signup, SignupStatus, Team, GameStats, GameStatus, RatingHistory
from app.db.database import async_session_maker

# =============================================================================
# HARDCODED GROUND TRUTH (from update_stats_g7.py + user corrections)
# team_a / team_b / team_c: partial name strings for matching
# =============================================================================
GAME_DATA = {
    1: {  # 17.01 | 3-team | 13:7:4 | Winner: A
        "team_a": ["Dias Bekbosyn", "Vlad Lishanlo", "Aldiyar Kazbekov", "Miras Mukanov", "Said Soltanzade", "Yernur Bauyrzhanuly"],
        "team_b": ["Arsen Kudaibergen", "Aidyn Galymbekov", "Umid Kamilov", "Daryn Bakyrkhan", "Zhanibek Xenbek", "Aktan"],
        "team_c": ["Alikhan Muratuly", "Yeldos Ismailov", "Asylbek Nurmagambetov", "Ansar Tanirbay", "Bakhtiyar Temirbayev", "Raimbek Sarzhakov"],
        "goals": {"Dias Bekbosyn": 5, "Vlad Lishanlo": 3, "Aldiyar Kazbekov": 2, "Miras Mukanov": 2,
                  "Said Soltanzade": 1, "Yernur Bauyrzhanuly": 1, "Arsen Kudaibergen": 3,
                  "Aidyn Galymbekov": 2, "Umid Kamilov": 1, "Zhanibek Xenbek": 1,
                  "Yeldos Ismailov": 2, "Bakhtiyar Temirbayev": 1, "Raimbek Sarzhakov": 1},
        "mvp": ["Dias Bekbosyn"],
    },
    2: {  # 24.01 | 2-team | 13:12 | Winner: A
        "team_a": ["Nurkabyl Sharipbay", "Said Soltanzade", "Mirlan Toktoshev", "Daryn Bakyrkhan",
                   "Yernur Bauyrzhanuly", "Aktan", "Zhanibek Xenbek", "Dastan Sadyraliyev", "Asylbek Nurmagambetov"],
        "team_b": ["Vlad Lishanlo", "Iliyas Akbergen", "Arsen Kudaibergen", "Aidyn Galymbekov",
                   "Yeldos Ismailov", "Yerik Yekibay", "Dias Bekbosyn", "Yermakhan Borankhan", "Adil Baizhanov"],
        "team_c": [],
        "goals": {"Nurkabyl Sharipbay": 7, "Said Soltanzade": 1, "Mirlan Toktoshev": 2,
                  "Vlad Lishanlo": 3, "Iliyas Akbergen": 2, "Arsen Kudaibergen": 2, "Aidyn Galymbekov": 2},
        "mvp": ["Nurkabyl Sharipbay"],
    },
    3: {  # 31.01 | 2-team | 8:11 | Winner: B
        # Score A=8 → Team A LOST; Score B=11 → Team B WON
        "team_a": ["Dastan Sadyraliyev", "Daryn Bakyrkhan", "Vlad Lishanlo", "Aidyn Galymbekov",
                   "Said Soltanzade", "Yerik Yekibay", "Asylbek Nurmagambetov", "Mansur Mutayev", "Raimbek Sarzhakov"],
        "team_b": ["Beka", "Bekmolda Daulet", "Asset Khassan", "Yermakhan Borankhan",
                   "Dias Bekbosyn", "Iliyas Akbergen", "Zhanibek Xenbek", "Viktor Snytkin", "Alikhan Muratuly"],
        "team_c": [],
        "goals": {"Asset Khassan": 1, "Iliyas Akbergen": 6, "Viktor Snytkin": 1,
                  "Daryn Bakyrkhan": 1, "Vlad Lishanlo": 3, "Aidyn Galymbekov": 1,
                  "Mansur Mutayev": 1, "Raimbek Sarzhakov": 1},
        "mvp": ["Iliyas Akbergen"],
    },
    4: {  # 07.02 | 2-team | 10:5 | Winner: A
        "team_a": ["Zhanibek Xenbek", "Vlad Lishanlo", "Daryn Bakyrkhan", "Bakhtiyar Temirbayev",
                   "Yernar Bestikpayev", "Said Soltanzade", "Dias August", "Dastan Sadyraliyev",
                   "Aidyn Galymbekov", "Raimbek Sarzhakov"],
        "team_b": ["Adok", "Akhmetov Dias", "Mansur Mutayev", "Medeu Yersain", "Yerik Yekibay",
                   "Yermakhan Borankhan", "Mirlan Toktoshev", "Bekmolda Daulet", "Viktor Snytkin", "Aktan"],
        "team_c": [],
        "goals": {"Zhanibek Xenbek": 1, "Vlad Lishanlo": 4, "Bakhtiyar Temirbayev": 2,
                  "Said Soltanzade": 1, "Dias August": 2, "Mansur Mutayev": 4, "Mirlan Toktoshev": 1},
        "mvp": ["Zhanibek Xenbek", "Adok"],
    },
    5: {  # 14.02 | 2-team | 10:13 | Winner: B
        # Score A=10 → Team A LOST; Score B=13 → Team B WON
        "team_a": ["Dastan Sadyraliyev", "Bekmolda Daulet", "Yermakhan Borankhan", "Niyaz Bayankulov",
                   "Aldiyar Kazbekov", "Mirlan Toktoshev", "Daryn Bakyrkhan", "Aidyn Galymbekov",
                   "Raimbek Sarzhakov", "Miras Mukanov"],
        "team_b": ["Iosif Vassilenko", "Akhmetov Dias", "Asset Khassan", "Dias Bekbosyn",
                   "Said Soltanzade", "Yerik Yekibay", "Dias Kaibar", "Viktor Snytkin",
                   "Vlad Lishanlo", "Asylbek Nurmagambetov"],
        "team_c": [],
        "goals": {"Said Soltanzade": 1, "Dias Kaibar": 4, "Viktor Snytkin": 4, "Vlad Lishanlo": 2,
                  "Asylbek Nurmagambetov": 2, "Aldiyar Kazbekov": 2, "Daryn Bakyrkhan": 1,
                  "Aidyn Galymbekov": 2, "Raimbek Sarzhakov": 1, "Miras Mukanov": 3},
        "mvp": ["Dias Kaibar", "Miras Mukanov"],
    },
    6: {  # 22.02 | 2-team | 5:5 | DRAW
        "team_a": ["Nurkabyl Sharipbay", "Miras Mukanov", "Iliyas Akbergen", "Adok",
                   "Dias Bekbosyn", "Mukhammed A Askar", "Niyaz Bayankulov", "Yermakhan Borankhan",
                   "Aidyn Kassym", "Alikhan Muratuly"],
        "team_b": ["Dias Kaibar", "Daryn Bakyrkhan", "Vlad Lishanlo", "Ansar Tanirbay",
                   "Aldiyar Kazbekov", "Mirlan Toktoshev", "Asset Khassan", "Almas Kaneshev",
                   "Yernar Bestikpayev", "Aktan"],
        "team_c": [],
        "goals": {"Nurkabyl Sharipbay": 4, "Miras Mukanov": 1, "Vlad Lishanlo": 1},
        "mvp": [],
    },
    7: {  # 28.02 | 2-team | 6:3 | Winner: A
        "team_a": ["Dastan Sadyraliyev", "Yernur Bauyrzhanuly", "Daryn Bakyrkhan", "Yernar Bestikpayev",
                   "Nurken", "Dias Bekbosyn", "Aidyn Galymbekov", "Iliyas Akbergen",
                   "Miras Mukanov", "Nurkabyl Sharipbay", "Mirlan Toktoshev"],
        "team_b": ["Aidyn Kassym", "Zhanibek Xenbek", "Niyaz Bayankulov", "Asset Khassan",
                   "Aldiyar Kazbekov", "Yeldos Ismailov", "Adok", "Bakhtiyar Temirbayev",
                   "Umid Kamilov", "Vlad Lishanlo"],
        "team_c": [],
        "goals": {"Nurkabyl Sharipbay": 3, "Miras Mukanov": 1, "Mirlan Toktoshev": 1,
                  "Adok": 1, "Vlad Lishanlo": 1, "Aldiyar Kazbekov": 1},
        "mvp": [],
    },
}


def find_user(users_by_name: dict, partial_name: str):
    """Find user by partial name (case-insensitive)."""
    partial_lower = partial_name.lower()
    # Exact match first
    for full_name, user in users_by_name.items():
        if full_name.lower() == partial_lower:
            return user
    # Partial match
    for full_name, user in users_by_name.items():
        if partial_lower in full_name.lower() or full_name.lower() in partial_lower:
            return user
    return None


async def main():
    async with async_session_maker() as s:
        print("=" * 70)
        print("🔧 FIXING HISTORICAL SIGNUPS + FULL RECALCULATION")
        print("=" * 70)

        # Load all users
        res = await s.execute(select(User))
        all_users = res.scalars().all()
        # Build name maps — prefer longer, more specific names
        users_by_name = {}
        for u in all_users:
            users_by_name[u.full_name] = u

        print(f"\n📦 Loaded {len(all_users)} users from DB\n")

        # ── STEP 1: Fix signups for games 1-7 ───────────────────────────
        print("🔧 Rebuilding signups and game_stats for games 1-7...")
        team_map = {"team_a": Team.A, "team_b": Team.B, "team_c": Team.C}

        for game_id, data in GAME_DATA.items():
            # Delete old signups and stats
            await s.execute(delete(Signup).where(Signup.game_id == game_id))
            await s.execute(delete(GameStats).where(GameStats.game_id == game_id))
            await s.flush()

            added = 0
            not_found = []
            all_teams = {**{name: "team_a" for name in data["team_a"]},
                         **{name: "team_b" for name in data["team_b"]},
                         **{name: "team_c" for name in data["team_c"]}}

            for player_name, team_key in all_teams.items():
                user = find_user(users_by_name, player_name)
                if not user:
                    not_found.append(player_name)
                    continue

                db_team = team_map[team_key]
                goals = data["goals"].get(player_name, 0)

                # Also check short name for goals
                if goals == 0:
                    for gname, gcount in data["goals"].items():
                        if gname.lower() in user.full_name.lower() or user.full_name.lower().split()[0] in gname.lower():
                            goals = gcount
                            break

                is_mvp = any(
                    mvp_name.lower() in user.full_name.lower() or user.full_name.lower().split()[0] in mvp_name.lower()
                    for mvp_name in data["mvp"]
                )

                signup = Signup(game_id=game_id, user_id=user.user_id,
                                status=SignupStatus.ACTIVE, team=db_team)
                stat = GameStats(game_id=game_id, user_id=user.user_id,
                                 goals=goals, is_mvp=is_mvp)
                s.add(signup)
                s.add(stat)
                added += 1

            if not_found:
                print(f"  ⚠️  Game {game_id}: NOT FOUND: {not_found}")
            print(f"  ✅ Game {game_id}: Added {added} players")

        await s.flush()
        print()

        # ── STEP 2: Recalculate all ratings ─────────────────────────────
        print("🔄 Resetting all users to 100 ELO, 0 games...")
        from sqlalchemy import text, update
        await s.execute(text("UPDATE users SET rating=100, games_played=0, stats_mvp=0, stats_matches=0"))
        await s.execute(delete(RatingHistory))
        await s.flush()

        games_res = await s.execute(
            select(Game).where(Game.status == GameStatus.FINISHED).order_by(Game.date_time.asc())
        )
        games = games_res.scalars().all()
        print(f"⚙️  Processing {len(games)} games...\n")

        for game in games:
            date_str = game.date_time.strftime('%d.%m.%Y')
            # Build team_points
            team_points = {}
            if game.team_count == 2:
                sa, sb = game.score_a or 0, game.score_b or 0
                if sa == sb:
                    team_points[Team.A] = 0; team_points[Team.B] = 0
                elif game.winner_team == Team.A:
                    team_points[Team.A] = 10; team_points[Team.B] = -5
                elif game.winner_team == Team.B:
                    team_points[Team.A] = -5; team_points[Team.B] = 10
                else:
                    team_points[Team.A] = 10 if sa > sb else -5
                    team_points[Team.B] = 10 if sb > sa else -5
            elif game.team_count == 3:
                scores = [(Team.A, game.score_a or 0), (Team.B, game.score_b or 0), (Team.C, game.score_c or 0)]
                unique = sorted(list(set(v for _, v in scores)), reverse=True)
                for t, sc in scores:
                    if len(unique) == 1:
                        team_points[t] = 0
                    else:
                        r = unique.index(sc)
                        team_points[t] = 10 if r == 0 else (0 if r == 1 else -5)

            mvp_res = await s.execute(
                select(GameStats).where(GameStats.game_id == game.id, GameStats.is_mvp == True)
            )
            mvp_ids = set(m.user_id for m in mvp_res.scalars().all())

            p_res = await s.execute(
                select(User, Signup.team)
                .join(Signup)
                .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
            )
            players_data = p_res.all()

            print(f"  Game #{game.id} ({date_str}) {game.score_a}:{game.score_b}"
                  + (f":{game.score_c}" if game.score_c is not None else "")
                  + f" → {game.winner_team.value if game.winner_team else 'DRAW'} | {len(players_data)} players")

            for user, team in players_data:
                old = user.rating
                base = team_points.get(team, 0)
                is_mvp = user.user_id in mvp_ids
                change = base + (5 if is_mvp else 0)
                if is_mvp:
                    user.stats_mvp += 1
                user.rating += change
                user.games_played += 1
                user.stats_matches += 1
                s.add(RatingHistory(user_id=user.user_id, game_id=game.id,
                                    old_rating=old, new_rating=user.rating, change=change))

        await s.commit()

        # ── FINAL LEADERBOARD ────────────────────────────────────────────
        print("\n" + "=" * 70)
        print("🏆 FINAL LEADERBOARD (Top 30)")
        print("=" * 70)
        ur = await s.execute(select(User).where(User.games_played > 0).order_by(User.rating.desc()))
        users = ur.scalars().all()
        print(f"\n{'#':<4} {'Name':<30} {'ELO':<8} {'Games':<8} {'MVP'}")
        print("-" * 58)
        for i, u in enumerate(users, 1):
            mvp = f"⭐{u.stats_mvp}" if u.stats_mvp else ""
            print(f"{i:<4} {u.full_name:<30} {u.rating:<8} {u.games_played:<8} {mvp}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
