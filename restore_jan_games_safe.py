import asyncio
import logging
import sys
import os
from datetime import datetime
from sqlalchemy import select, text, func

# Setup Path
sys.path.insert(0, os.getcwd())

from app.db.database import async_session_maker
from app.db.models import User, Game, Signup, SignupStatus, Team, GameStats, GameStatus, Chat, RatingHistory, Vote

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DATA FROM manage_past_games.py
GAME_1 = {
    "id": 1,
    "date": "2026-01-17 11:00",
    "location": "Sportovní centrum Prosek | Litvínovská 500",
    "winner_team": Team.A,
    "ranking": [Team.A, Team.B, Team.C],
    "score_a": 13, "score_b": 7, "score_c": 4,
    "mvp": "Dias Bekbosyn",
    "team_a": { "members": ["Dias Bekbosyn", "Vlad Lishanlo", "Aldiyar Kazbekov", "Miras Mukanov", "Said Soltanzade", "Yernur Bauyrzhanuly"], "goals": {"Dias Bekbosyn": 5, "Vlad Lishanlo": 3, "Aldiyar Kazbekov": 2, "Miras Mukanov": 2, "Said Soltanzade": 1, "Yernur Bauyrzhanuly": 1}},
    "team_b": { "members": ["Arsen Kudaibergen", "Aidyn Galymbekov", "Umid Kamilov", "Daryn Bakyrkhan", "Zhanibek Xenbek", "Aktan Abdullaatov"], "goals": {"Arsen Kudaibergen": 3, "Aidyn Galymbekov": 2, "Umid Kamilov": 1, "Daryn Bakyrkhan": 0, "Zhanibek Xenbek": 1, "Aktan Abdullaatov": 0}},
    "team_c": { "members": ["Alikhan Muratuly", "Yeldos Ismailov", "Assylbek Nurmagambetov", "Ansar Tanirbay", "Bakhtiyar Temirbayev", "Raimbek Sarzhakov"], "goals": {"Alikhan Muratuly": 0, "Yeldos Ismailov": 2, "Assylbek Nurmagambetov": 0, "Ansar Tanirbay": 0, "Bakhtiyar Temirbayev": 1, "Raimbek Sarzhakov": 1}}
}

GAME_2 = {
    "id": 3,
    "date": "2026-01-24 11:00",
    "location": "Plamínkové 1593/2, 140 00 Praha 4-Nusle",
    "winner_team": Team.A,
    "ranking": [Team.A, Team.B],
    "score_a": 13, "score_b": 12, "score_c": None,
    "mvp": "Nurkabyl Sharipbay",
    "team_a": { "members": ["Nurkabyl Sharipbay", "Said Soltanzade", "Mirlan Toktoshev", "Daryn Bakyrkhan", "Yernur Bauyrzhanuly", "Aktan Abdullaatov", "Zhanibek Xenbek", "Dastan Sadyraliyev", "Assylbek Nurmagambetov"], "goals": {"Nurkabyl Sharipbay": 7, "Said Soltanzade": 1, "Mirlan Toktoshev": 2, "Daryn Bakyrkhan": 0, "Yernur Bauyrzhanuly": 0, "Aktan Abdullaatov": 0, "Zhanibek Xenbek": 0, "Dastan Sadyraliyev": 0, "Assylbek Nurmagambetov": 0}},
    "team_b": { "members": ["Vlad Lishanlo", "Iliyas Akbergen", "Arsen Kudaibergen", "Aidyn Galymbekov", "Yeldos Ismailov", "Yerik Yekibay", "Dias Bekbosyn", "Yermakhan Borankhan", "Adil Baizhanov"], "goals": {"Vlad Lishanlo": 3, "Iliyas Akbergen": 2, "Arsen Kudaibergen": 2, "Aidyn Galymbekov": 2, "Yeldos Ismailov": 0, "Yerik Yekibay": 0, "Dias Bekbosyn": 0, "Yermakhan Borankhan": 0, "Adil Baizhanov": 0}}
}

GAME_3 = {
    "id": 4,
    "date": "2026-01-31 11:00",
    "location": "Plaminkove 1593/2, 140 00 Praha 4-Nusle",
    "winner_team": Team.B,
    "ranking": [Team.B, Team.A],
    "score_a": 8, "score_b": 11, "score_c": None,
    "mvp": "Iliyas Akbergen",
    "team_a": { "members": ["Vlad Lishanlo", "Raimbek Sarzhakov", "Aidyn Galymbekov", "Daryn Bakyrkhan", "Mansur Mutayev", "Dastan Sadyraliyev", "Said Soltanzade", "Yerik Yekibay", "Assylbek Nurmagambetov"], "goals": {"Vlad Lishanlo": 3, "Raimbek Sarzhakov": 1, "Aidyn Galymbekov": 1, "Daryn Bakyrkhan": 1, "Mansur Mutayev": 1, "Dastan Sadyraliyev": 0, "Said Soltanzade": 0, "Yerik Yekibay": 0, "Assylbek Nurmagambetov": 0}},
    "team_b": { "members": ["Iliyas Akbergen", "Dias Bekbosyn", "Viktor Snytkin", "Asset Khassan", "Daulet Bekmolda", "Yermakhan Borankhan", "Zhanibek Xenbek", "Alikhan Muratuly", "Beka"], "goals": {"Iliyas Akbergen": 6, "Dias Bekbosyn": 2, "Viktor Snytkin": 1, "Asset Khassan": 1, "Daulet Bekmolda": 0, "Yermakhan Borankhan": 0, "Zhanibek Xenbek": 0, "Alikhan Muratuly": 0, "Beka": 0}}
}

ALL_GAMES = [GAME_1, GAME_2, GAME_3]

async def resolve_user(session, ident):
    if not ident: return None
    ident = ident.strip()
    stmt = select(User).where(func.lower(User.full_name) == ident.lower())
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if user: return user
    stmt = select(User).where(User.full_name.ilike(f"%{ident}%"))
    res = await session.execute(stmt)
    user = res.scalars().first()
    if user: return user
    return None

async def run_restore():
    async with async_session_maker() as session:
        print("=== 🛠 RESTORING JANUARY GAMES (SAFE MODE) 🛠 ===")
        
        # Get Chat and Admin
        chat = (await session.execute(select(Chat))).scalars().first()
        admin = (await session.execute(select(User))).scalars().first()
        
        for g_data in ALL_GAMES:
            dt = datetime.strptime(g_data["date"], "%Y-%m-%d %H:%M")
            print(f"\nRestoring Game ID {g_data['id']} ({dt})...")
            
            # 1. Create Game
            game = Game(
                id=g_data['id'],
                chat_id=chat.chat_id if chat else -1,
                created_by=admin.user_id if admin else 0,
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
            await session.flush()
            
            teams_map = {Team.A: g_data["team_a"], Team.B: g_data["team_b"]}
            if "team_c" in g_data: teams_map[Team.C] = g_data["team_c"]
            ranking = g_data["ranking"]
            
            for team_enum, t_info in teams_map.items():
                for p_name in t_info["members"]:
                    user = await resolve_user(session, p_name)
                    if not user:
                        print(f"  ⚠️ User NOT FOUND: {p_name}")
                        continue
                    
                    # 2. Add Signup
                    session.add(Signup(game_id=game.id, user_id=user.user_id, status=SignupStatus.ACTIVE, team=team_enum))
                    
                    # 3. Add Stats
                    goals = t_info["goals"].get(p_name, 0)
                    is_mvp = (p_name == g_data["mvp"])
                    if goals > 0 or is_mvp:
                        session.add(GameStats(game_id=game.id, user_id=user.user_id, goals=goals, is_mvp=is_mvp))
                    
                    # 4. Add RatingHistory (NO actual user rating update)
                    change = 0
                    if game.team_count == 2:
                        change = 10 if team_enum == g_data["winner_team"] else -5
                    else:
                        if team_enum == ranking[0]: change = 10
                        elif team_enum == ranking[1]: change = 0
                        else: change = -5
                    if is_mvp: change += 5
                    
                    # We don't know the exact old_rating at the time without complex math,
                    # but for history view, new_rating = old_rating + change.
                    # We can use placeholder or current-change.
                    # Actually, RatingHistory just needs a record to show in /my_history.
                    session.add(RatingHistory(
                        user_id=user.user_id,
                        game_id=game.id,
                        old_rating=0, # History view usually just shows 'change'
                        new_rating=0,
                        change=change
                    ))
            
        await session.commit()
        print("\n=== ✨ RESTORATION COMPLETE ✨ ===")

if __name__ == "__main__":
    asyncio.run(run_restore())
