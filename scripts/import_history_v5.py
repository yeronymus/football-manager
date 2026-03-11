import asyncio
import os
import sys
import datetime
from datetime import timezone

# Setup path
sys.path.append(os.getcwd())
sys.path.append("/app")

from app.db.database import async_session_maker
from app.db.models import Game, Signup, GameStats, Team, GameStatus, User, Chat, SignupStatus
from sqlalchemy import text, select

# THE DEFINITIVE DATA
games_raw = [
    {
        "id": 1, "date": "2026-01-17", "score": "13:7:4", 
        "W": ["Dias Bekbosyn","Vlad Lishanlo","Aldiyar Kazbekov","Miras Mukanov","Said Soltanzade","Yernur Bauyrzhanuly"],
        "L": ["Arsen Kudaibergen","Aidyn Galymbekov","Umid Kamilov","Daryn Bakyrkhan","Zhanibek Xenbek","Aktan Abdullaatov","Alikhan Muratuly","Yeldos Ismailov","Assylbek Nurmagambetov","Ansar Tanirbay","Bakhtiyar Temirbayev","Raimbek Sarzhakov"],
        "goals": {"Dias Bekbosyn":5,"Vlad Lishanlo":3,"Aldiyar Kazbekov":2,"Miras Mukanov":2,"Said Soltanzade":1,"Yernur Bauyrzhanuly":1,"Arsen Kudaibergen":3,"Aidyn Galymbekov":2,"Umid Kamilov":1,"Zhanibek Xenbek":1,"Yeldos Ismailov":2,"Bakhtiyar Temirbayev":1,"Raimbek Sarzhakov":1},
        "mvp": ["Dias Bekbosyn"]
    },
    {
        "id": 2, "date": "2026-01-24", "score": "13:12", 
        "W": ["Nurkabyl Sharipbay","Said Soltanzade","Mirlan Toktoshev","Daryn Bakyrkhan","Yernur Bauyrzhanuly","Aktan Abdullaatov","Zhanibek Xenbek","Dastan Sadyraliyev","Assylbek Nurmagambetov"],
        "L": ["Vlad Lishanlo","Iliyas Akbergen","Arsen Kudaibergen","Aidyn Galymbekov","Yeldos Ismailov","Yerik Yekibay","Dias Bekbosyn","Yermakhan Borankhan","Adil Baizhanov"],
        "goals": {"Nurkabyl Sharipbay":7,"Said Soltanzade":1,"Mirlan Toktoshev":2,"Vlad Lishanlo":3,"Iliyas Akbergen":2,"Arsen Kudaibergen":2,"Aidyn Galymbekov":2},
        "mvp": ["Nurkabyl Sharipbay"]
    },
    {
        "id": 3, "date": "2026-01-31", "score": "8:11", 
        "W": ["Beka","Daulet Bekmolda","Asset Khassan","Yermakhan Borankhan","Dias Bekbosyn","Iliyas Akbergen","Zhanibek Xenbek","Viktor Snytkin","Alikhan Muratuly"],
        "L": ["Dastan Sadyraliyev","Daryn Bakyrkhan","Vlad Lishanlo","Aidyn Galymbekov","Said Soltanzade","Yerik Yekibay","Assylbek Nurmagambetov","Mansur Mutayev","Raimbek Sarzhakov"],
        "goals": {"Asset Khassan":1,"Iliyas Akbergen":6,"Viktor Snytkin":1,"Daryn Bakyrkhan":1,"Vlad Lishanlo":3,"Aidyn Galymbekov":1,"Mansur Mutayev":1,"Raimbek Sarzhakov":1},
        "mvp": ["Iliyas Akbergen"]
    },
    {
        "id": 4, "date": "2026-02-08", "score": "10:5", 
        "W": ["Zhanibek Xenbek","Vlad Lishanlo","Daryn Bakyrkhan","Bakhtiyar Temirbayev","Yernar Bestikpayev","Said Soltanzade","Dias August","Dastan Sadyraliyev","Aidyn Galymbekov","Raimbek Sarzhakov"],
        "L": ["Adok Salimzhan","Akhmetov Dias","Mansur Mutayev","Medeu Yersain","Yerik Yekibay","Yermakhan Borankhan","Mirlan Toktoshev","Daulet Bekmolda","Viktor Snytkin","Aktan Abdullaatov"],
        "goals": {"Zhanibek Xenbek":1,"Vlad Lishanlo":4,"Bakhtiyar Temirbayev":2,"Said Soltanzade":1,"Dias August":2,"Mansur Mutayev":4,"Mirlan Toktoshev":1},
        "mvp": ["Zhanibek Xenbek", "Adok Salimzhan"]
    },
    {
        "id": 5, "date": "2026-02-14", "score": "10:13", 
        "W": ["Iosif Vassilenko","Akhmetov Dias","Asset Khassan","Dias Bekbosyn","Said Soltanzade","Yerik Yekibay","Dias Kaibar","Viktor Snytkin","Vlad Lishanlo","Assylbek Nurmagambetov"],
        "L": ["Dastan Sadyraliyev","Daulet Bekmolda","Yermakhan Borankhan","Niyaz Bayankulov","Aldiyar Kazbekov","Mirlan Toktoshev","Daryn Bakyrkhan","Aidyn Galymbekov","Raimbek Sarzhakov","Miras Mukanov"],
        "goals": {"Said Soltanzade":1,"Dias Kaibar":4,"Viktor Snytkin":4,"Vlad Lishanlo":2,"Assylbek Nurmagambetov":2,"Aldiyar Kazbekov":2,"Daryn Bakyrkhan":1,"Aidyn Galymbekov":2,"Raimbek Sarzhakov":1,"Miras Mukanov":3},
        "mvp": ["Dias Kaibar", "Miras Mukanov"]
    },
    {
        "id": 6, "date": "2026-02-21", "score": "5:5", "W": [], "L": [],
        "D": ["Nurkabyl Sharipbay","Miras Mukanov","Iliyas Akbergen","Adok Salimzhan","Dias Bekbosyn","Mukhammed A Askar","Niyaz Bayankulov","Yermakhan Borankhan","Aidyn Kassym","Alikhan Muratuly", "Dias Kaibar","Daryn Bakyrkhan","Vlad Lishanlo","Ansar Tanirbay","Aldiyar Kazbekov","Mirlan Toktoshev","Asset Khassan","Almas Kaneshev","Yernar Bestikpayev","Aktan Abdullaatov"],
        "goals": {"Nurkabyl Sharipbay":4,"Miras Mukanov":1,"Vlad Lishanlo":1},
        "mvp": [] 
    },
    {
        "id": 7, "date": "2026-02-28", "score": "6:3", 
        "W": ["Dastan Sadyraliyev", "Yernur Bauyrzhanuly", "Daryn Bakyrkhan", "Yernar Bestikpayev", "Nurken Samigullin", "Dias Bekbosyn", "Aidyn Galymbekov", "Iliyas Akbergen", "Miras Mukanov", "Nurkabyl Sharipbay", "Mirlan Toktoshev"],
        "L": ["Aidyn Kassym", "Zhanibek Xenbek", "Niyaz Bayankulov", "Asset Khassan", "Aldiyar Kazbekov", "Yeldos Ismailov", "Adok Salimzhan", "Bakhtiyar Temirbayev", "Umid Kamilov", "Vlad Lishanlo"],
        "goals": {"Nurkabyl Sharipbay":3, "Miras Mukanov":1, "Mirlan Toktoshev":1, "Adok Salimzhan":1, "Vlad Lishanlo":1, "Aldiyar Kazbekov":1},
        "mvp": []
    }
]

async def run_import():
    output = []
    try:
        async with async_session_maker() as session:
            output.append("Cleaning up match history...")
            await session.execute(text("TRUNCATE TABLE game_stats, signups, games RESTART IDENTITY CASCADE"))
            await session.commit()

            # Ensure archive chat exists
            archive_chat_id = -1000000000001
            chat_res = await session.execute(select(Chat).where(Chat.chat_id == archive_chat_id))
            chat = chat_res.scalar_one_or_none()
            if not chat:
                chat = Chat(chat_id=archive_chat_id, title="Archive History")
                session.add(chat)
                await session.commit()

            # Build user map
            users_res = await session.execute(select(User))
            users = users_res.scalars().all()
            user_map = {u.full_name.strip().lower(): u for u in users}
            output.append(f"Mapped {len(user_map)} users from DB.")

            creator_id = users[0].user_id if users else 1

            for g_data in games_raw:
                score_parts = g_data['score'].split(':')
                s_a = int(score_parts[0])
                s_b = int(score_parts[1])
                s_c = int(score_parts[2]) if len(score_parts) > 2 else 0
                
                dt = datetime.datetime.strptime(g_data['date'], "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=10, minute=0)
                
                w_list = g_data.get('W', [])
                l_list = g_data.get('L', [])
                d_list = g_data.get('D', [])
                
                winner_team = None
                if w_list:
                    winner_team = Team.A
                
                game = Game(
                    id=g_data['id'],
                    chat_id=archive_chat_id,
                    created_by=creator_id,
                    date_time=dt,
                    location=f"Game {g_data['id']} (Archive)",
                    status=GameStatus.FINISHED,
                    score_a=s_a,
                    score_b=s_b,
                    score_c=s_c,
                    winner_team=winner_team,
                    team_count=3 if s_c > 0 else 2
                )
                session.add(game)
                await session.flush()
                
                mvp_list = g_data.get('mvp', [])
                goals_map = g_data.get('goals', {})
                
                # Helper to add players
                async def add_players(names, team):
                    added = 0
                    for name in names:
                        clean_name = name.strip().lower()
                        if clean_name in user_map:
                            u = user_map[clean_name]
                            # Signup
                            signup = Signup(
                                game_id=game.id,
                                user_id=u.user_id,
                                status=SignupStatus.ACTIVE,
                                team=team
                            )
                            session.add(signup)
                            # Stats
                            stat = GameStats(
                                game_id=game.id,
                                user_id=u.user_id,
                                goals=goals_map.get(name, 0),
                                is_mvp=(name in mvp_list)
                            )
                            session.add(stat)
                            added += 1
                    return added

                cnt = 0
                cnt += await add_players(w_list, Team.A)
                cnt += await add_players(l_list, Team.B)
                cnt += await add_players(d_list, Team.A) # Draws on A
                output.append(f"Game {g_data['id']}: Added {cnt} players.")
            
            await session.commit()
            output.append("IMPORT COMPLETED SUCCESSFULLY")
    except Exception as e:
        output.append(f"ERROR: {e}")
        import traceback
        output.append(traceback.format_exc())
    finally:
        print("\n".join(output))

if __name__ == '__main__':
    asyncio.run(run_import())
