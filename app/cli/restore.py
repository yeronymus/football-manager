import asyncio
import logging
from datetime import datetime
from sqlalchemy import select, delete, text, func
from app.db.database import async_session_maker
from app.db.models import User, Game, Signup, SignupStatus, Team, GameStats, GameStatus, Chat, RatingHistory, Vote

logger = logging.getLogger(__name__)

# ==========================================
# 📂 DATA FOR RESTORATION (The Golden Source)
# ==========================================

# 1️⃣ Game 17.01.2026 (Prosek, 3 teams)
GAME_1 = {
    "date": "2026-01-17 11:00",
    "location": "Sportovní centrum Prosek | Litvínovská 500",
    "winner_team": Team.A, # Orange
    "ranking": [Team.A, Team.B, Team.C], # 1st: Orange, 2nd: Green, 3rd: Blue
    "score_a": 13, "score_b": 7,"score_c": 4,
    "mvp": "Dias Bekbosyn",
    # Teams
    "team_a": { # Orange (Winner +10)
        "members": ["Dias Bekbosyn", "Vlad Lishanlo", "Aldiyar Kazbekov", "Miras Mukanov", "Said Soltanzade", "Yernur Bauyrzhanuly"],
        "goals": {"Dias Bekbosyn": 5, "Vlad Lishanlo": 3, "Aldiyar Kazbekov": 2, "Miras Mukanov": 2, "Said Soltanzade": 1, "Yernur Bauyrzhanuly": 1}
    },
    "team_b": { # Green (2nd 0)
        "members": ["Arsen Kudaibergen", "Aidyn Galymbekov", "Umid Kamilov", "Daryn Bakyrkhan", "Zhanibek Xenbek", "Aktan Abdullaatov"],
        "goals": {"Arsen Kudaibergen": 3, "Aidyn Galymbekov": 2, "Umid Kamilov": 1, "Daryn Bakyrkhan": 0, "Zhanibek Xenbek": 1, "Aktan Abdullaatov": 0}
    },
    "team_c": { # Blue (3rd -5)
        "members": ["Alikhan Muratuly", "Yeldos Ismailov", "Assylbek Nurmagambetov", "Ansar Tanirbay", "Bakhtiyar Temirbayev", "Raimbek Sarzhakov"],
        "goals": {"Alikhan Muratuly": 0, "Yeldos Ismailov": 2, "Assylbek Nurmagambetov": 0, "Ansar Tanirbay": 0, "Bakhtiyar Temirbayev": 1, "Raimbek Sarzhakov": 1}
    }
}

# 2️⃣ Game 24.01.2026 (Plaminkove, 2 teams)
GAME_2 = {
    "date": "2026-01-24 11:00",
    "location": "Plamínkové 1593/2, 140 00 Praha 4-Nusle",
    "winner_team": Team.A, # Red (Winner)
    "ranking": [Team.A, Team.B],
    "score_a": 13, "score_b": 12, "score_c": None,
    "mvp": "Nurkabyl Sharipbay",
    "team_a": { # Red (Winner +10)
        "members": ["Nurkabyl Sharipbay", "Said Soltanzade", "Mirlan Toktoshev", "Daryn Bakyrkhan", "Yernur Bauyrzhanuly", "Aktan Abdullaatov", "Zhanibek Xenbek", "Dastan Sadyraliyev", "Assylbek Nurmagambetov"],
        "goals": {"Nurkabyl Sharipbay": 7, "Said Soltanzade": 1, "Mirlan Toktoshev": 2, "Daryn Bakyrkhan": 0, "Yernur Bauyrzhanuly": 0, "Aktan Abdullaatov": 0, "Zhanibek Xenbek": 0, "Dastan Sadyraliyev": 0, "Assylbek Nurmagambetov": 0}
    },
    "team_b": { # Green (Loser -5)
        "members": ["Vlad Lishanlo", "Iliyas Akbergen", "Arsen Kudaibergen", "Aidyn Galymbekov", "Yeldos Ismailov", "Yerik Yekibay", "Dias Bekbosyn", "Yermakhan Borankhan", "Adil Baizhanov"],
        "goals": {"Vlad Lishanlo": 3, "Iliyas Akbergen": 2, "Arsen Kudaibergen": 2, "Aidyn Galymbekov": 2, "Yeldos Ismailov": 0, "Yerik Yekibay": 0, "Dias Bekbosyn": 0, "Yermakhan Borankhan": 0, "Adil Baizhanov": 0}
    }
}

# 3️⃣ Game 31.01.2026 (Plaminkove, 2 teams)
GAME_3 = {
    "date": "2026-01-31 11:00",
    "location": "Plaminkove 1593/2, 140 00 Praha 4-Nusle",
    "winner_team": Team.B, # Green (Winner)
    "ranking": [Team.B, Team.A],
    "score_a": 8, "score_b": 11, "score_c": None,
    "mvp": "Iliyas Akbergen",
    "team_a": { # Orange (Loser -5)
        "members": ["Vlad Lishanlo", "Raimbek Sarzhakov", "Aidyn Galymbekov", "Daryn Bakyrkhan", "Mansur Mutayev", "Dastan Sadyraliyev", "Said Soltanzade", "Yerik Yekibay", "Assylbek Nurmagambetov"],
        "goals": {"Vlad Lishanlo": 3, "Raimbek Sarzhakov": 1, "Aidyn Galymbekov": 1, "Daryn Bakyrkhan": 1, "Mansur Mutayev": 1, "Dastan Sadyraliyev": 0, "Said Soltanzade": 0, "Yerik Yekibay": 0, "Assylbek Nurmagambetov": 0}
    },
    "team_b": { # Green (Winner +10)
        "members": ["Iliyas Akbergen", "Dias Bekbosyn", "Viktor Snytkin", "Asset Khassan", "Daulet Bekmolda", "Yermakhan Borankhan", "Zhanibek Xenbek", "Alikhan Muratuly", "Beka"],
        "goals": {"Iliyas Akbergen": 6, "Dias Bekbosyn": 2, "Viktor Snytkin": 1, "Asset Khassan": 1, "Daulet Bekmolda": 0, "Yermakhan Borankhan": 0, "Zhanibek Xenbek": 0, "Alikhan Muratuly": 0, "Beka": 0}
    }
}

ALL_GAMES = [GAME_1, GAME_2, GAME_3]

async def resolve_user(session, ident):
    if not ident: return None
    ident = ident.strip()
    
    # 1. Exact match (case insensitive)
    stmt = select(User).where(func.lower(User.full_name) == ident.lower())
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if user: return user
    
    # 2. Contains match (for 'Beka' -> 'Beka ...')
    stmt = select(User).where(User.full_name.ilike(f"%{ident}%"))
    res = await session.execute(stmt)
    user = res.scalars().first()
    if user: return user
    
    return None

async def restore_january_2026():
    """Restores data for January 2026."""
    async with async_session_maker() as session:
        print("=== 🚨 STARTING HARD RESET FOR JANUARY 2026 🚨 ===")
        
        # 1. DELETE ALL DATA FOR JAN 2026
        # Find all games in Jan 2026
        stmt = select(Game.id).where(
            Game.date_time >= datetime(2026, 1, 1),
            Game.date_time < datetime(2026, 2, 1)
        )
        game_ids = (await session.execute(stmt)).scalars().all()
        
        if game_ids:
            print(f"🗑️ Deleting {len(game_ids)} games {game_ids} and related data...")
            await session.execute(delete(GameStats).where(GameStats.game_id.in_(game_ids)))
            await session.execute(delete(Signup).where(Signup.game_id.in_(game_ids)))
            await session.execute(delete(RatingHistory).where(RatingHistory.game_id.in_(game_ids)))
            await session.execute(delete(Vote).where(Vote.game_id.in_(game_ids)))
            await session.execute(delete(Game).where(Game.id.in_(game_ids)))
        else:
            print("ℹ️ No games found for Jan 2026 to delete.")

        # 2. RESET ALL USERS STATS TO ZERO/BASELINE
        print("🔄 Resetting ALL users to baseline (100 MMR, 0 Games)...")
        await session.execute(text("UPDATE users SET rating = 100, games_played = 0, stats_mvp = 0, stats_matches = 0"))
        
        await session.commit()
        print("✅ Data Wiped. Ready to Restore.")
        
        # Get Admin and Chat info for FKs
        chat = (await session.execute(select(Chat))).scalars().first()
        admin = (await session.execute(select(User))).scalars().first()
        if not chat or not admin:
            print("❌ Critical: No Chat or Admin found in DB. Cannot insert games.")
            return

        # 3. RESTORE GAMES LOOP
        for i, g_data in enumerate(ALL_GAMES, 1):
            dt = datetime.strptime(g_data["date"], "%Y-%m-%d %H:%M")
            print(f"\nExample {i}: Restoring Game {dt}...")
            
            # Create Game
            game = Game(
                chat_id=chat.chat_id,
                created_by=admin.user_id,
                date_time=dt,
                location=g_data["location"],
                status=GameStatus.FINISHED,
                team_count=3 if "team_c" in g_data else 2,
                winner_team=g_data["winner_team"],
                score_a=g_data["score_a"],
                score_b=g_data["score_b"],
                score_c=g_data.get("score_c"),
                gk_hours=24
            )
            session.add(game)
            await session.flush() # Get ID
            
            # Map Team Data
            teams_map = {Team.A: g_data["team_a"], Team.B: g_data["team_b"]}
            if "team_c" in g_data: teams_map[Team.C] = g_data["team_c"]
            
            ranking = g_data["ranking"]
            
            # Process Players
            for team_enum, t_info in teams_map.items():
                for p_name in t_info["members"]:
                    user = await resolve_user(session, p_name)
                    if not user:
                        print(f"  ⚠️ User NOT FOUND: {p_name} (skipping)")
                        continue
                    
                    # Add Signup
                    session.add(Signup(game_id=game.id, user_id=user.user_id, status=SignupStatus.ACTIVE, team=team_enum))
                    
                    # Add Goals Stats
                    goals = t_info["goals"].get(p_name, 0)
                    is_mvp = (p_name == g_data["mvp"])
                    
                    if goals > 0 or is_mvp:
                        u_stats = GameStats(game_id=game.id, user_id=user.user_id, goals=goals, is_mvp=is_mvp)
                        session.add(u_stats)
                    
                    # CALCULATE MMR CHANGE
                    change = 0
                    if game.team_count == 2:
                        if game.score_a == game.score_b:
                            change = 0
                        elif team_enum == g_data["winner_team"]:
                            change = 10
                        else:
                            change = -5
                    else:
                        # 3 Teams logic with tie handling
                        scores = [(Team.A, g_data["score_a"] or 0), (Team.B, g_data["score_b"] or 0), (Team.C, g_data["score_c"] or 0)]
                        unique_scores = sorted(list(set(s[1] for s in scores)), reverse=True)
                        score = t_info.get("score") or (g_data["score_a"] if team_enum == Team.A else g_data["score_b"] if team_enum == Team.B else g_data["score_c"])
                        
                        if len(unique_scores) == 1:
                            change = 0
                        else:
                            rank = unique_scores.index(score)
                            if rank == 0: change = 10
                            elif rank == 1: change = 0
                            else: change = -5
                            
                    # MVP Bonus

                    if is_mvp:
                        change += 5
                        user.stats_mvp += 1

                    # Update User Profile
                    old_rating = user.rating
                    user.rating += change
                    user.games_played += 1
                    user.stats_matches += 1
                    
                    # Add History
                    session.add(RatingHistory(
                        user_id=user.user_id,
                        game_id=game.id,
                        old_rating=old_rating,
                        new_rating=user.rating,
                        change=change
                    ))
                    
                    print(f"    -> {p_name}: {old_rating} -> {user.rating} ({'+' if change>0 else ''}{change}) [G:{goals}, MVP:{'Yes' if is_mvp else 'No'}]")

        await session.commit()
        print("\n=== ✨ RESTORATION COMPLETE ✨ ===")
        
        # 4. VERIFICATION
        print("\n📊 VERIFICATION CHECK:")
        check_users = ["Daryn Bakyrkhan", "Raimbek Sarzhakov", "Viktor Snytkin", "Dias Bekbosyn"]
        for name in check_users:
            u = await resolve_user(session, name)
            if u:
                print(f"  🔹 {u.full_name}: Games: {u.games_played}, Rating: {u.rating} (Expected: Check T-Z)")
            else:
                print(f"  ❌ {name} not found in DB")
