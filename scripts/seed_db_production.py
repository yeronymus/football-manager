import os
import sys
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db, engine
from app.db.models import User, Position, Base
from sqlalchemy.orm import Session
from sqlalchemy import text

# Initialize schemas
Base.metadata.create_all(bind=engine)

# Player handles mapping from user request
TELEGRAM_USERS = {
    "Adil Baizhanov": "Baizhanov9",
    "Adok Salimzhan": "Adok111",
    "Aidyn Galymbekov": "AidoXo",
    "Akhmetov Dias": "zzzzzx45",
    "Aktan Abdullaatov": "abdulatovvv",
    "Aldiyar Kazbekov": "siemens11",
    "Alikhan Muratuly": "muratuly095",
    "Amir Rustam": "ten7ek",
    "Ansar Tanirbay": "tanirbay",
    "Arsen Kudaibergen": "kdbr_a",
    "Asset Khassan": "asset14",
    "Assylbek Nurmagambetov": "somniumfides",
    "Bakhtiyar Temirbayev": "Bahonnn",
    "Daryn Bakyrkhan": "daryn_bt",
    "Dastan Sadyraliyev": "sadyrdas",
    "Daulet Bekmolda": "Dvuletik",
    "Dias August": "august_dias",
    "Dias Bekbosyn": "diasbekbosyn",
    "Iliyas Akbergen": "yaniskegelbar",
    "Iosif Vassilenko": "iosifvv",
    "Mansur Mutayev": "Mansurzito",
    "Medeu Yersain": "w1thoutme66",
    "Miras Mukanov": "mukanovmrs",
    "Mirlan Toktoshev": "mtoktosheeevv1",
    "Mukhammed A Askar": "mukhvmmed",
    "Nurkabyl Sharipbay": "Noori_28",
    "Raimbek Sarzhakov": "raim4real",
    "Said Soltanzade": "skazal1337",
    "Umid Kamilov": "kamilov31",
    "Viktor Snytkin": "matumba06",
    "Vlad Lishanlo": "lishanlo",
    "Yeldos Ismailov": "yeldos_1",
    "Yerik Yekibay": "kirey0606",
    "Yermakhan Borankhan": "borankhann",
    "Yernar Bestikpayev": "napovorotenapravo",
    "Yernur Bauyrzhanuly": "yeronym",
    "Zhanibek Xenbek": "saddam_4ort",
    "Nurken Samigullin": "nurkennuq",
    "Beka": None,
    "Daulet Bekmolda": "Dvuletik",
    "Aidyn Kassym": "s_1dero",
    "Almas Kaneshev": "kaneshev",
    "Dias Kaibar": "deep_pernul",
    "Niyaz Bayankulov": "the_niyaz",
    "Nurislam": "nurisss123",
    "Rauan Tanov": "rautnv888"
}

# The hardcoded stats calculated for Games 1-7
# We run the logic here to guarantee fresh calculation and easy seeding.
games_raw = [
    {
        "id": 1, "score": "13:7:4", "W": ["Dias Bekbosyn","Vlad Lishanlo","Aldiyar Kazbekov","Miras Mukanov","Said Soltanzade","Yernur Bauyrzhanuly"],
        "L": ["Arsen Kudaibergen","Aidyn Galymbekov","Umid Kamilov","Daryn Bakyrkhan","Zhanibek Xenbek","Aktan Abdullaatov","Alikhan Muratuly","Yeldos Ismailov","Assylbek Nurmagambetov","Ansar Tanirbay","Bakhtiyar Temirbayev","Raimbek Sarzhakov"],
        "goals": {"Dias Bekbosyn":5,"Vlad Lishanlo":3,"Aldiyar Kazbekov":2,"Miras Mukanov":2,"Said Soltanzade":1,"Yernur Bauyrzhanuly":1,"Arsen Kudaibergen":3,"Aidyn Galymbekov":2,"Umid Kamilov":1,"Zhanibek Xenbek":1,"Yeldos Ismailov":2,"Bakhtiyar Temirbayev":1,"Raimbek Sarzhakov":1},
        "mvp": ["Dias Bekbosyn"]
    },
    {
        "id": 2, "score": "13:12", "W": ["Nurkabyl Sharipbay","Said Soltanzade","Mirlan Toktoshev","Daryn Bakyrkhan","Yernur Bauyrzhanuly","Aktan Abdullaatov","Zhanibek Xenbek","Dastan Sadyraliyev","Assylbek Nurmagambetov"],
        "L": ["Vlad Lishanlo","Iliyas Akbergen","Arsen Kudaibergen","Aidyn Galymbekov","Yeldos Ismailov","Yerik Yekibay","Dias Bekbosyn","Yermakhan Borankhan","Adil Baizhanov"],
        "goals": {"Nurkabyl Sharipbay":7,"Said Soltanzade":1,"Mirlan Toktoshev":2,"Vlad Lishanlo":3,"Iliyas Akbergen":2,"Arsen Kudaibergen":2,"Aidyn Galymbekov":2},
        "mvp": ["Nurkabyl Sharipbay"]
    },
    {
        "id": 3, "score": "8:11", "W": ["Beka","Daulet Bekmolda","Asset Khassan","Yermakhan Borankhan","Dias Bekbosyn","Iliyas Akbergen","Zhanibek Xenbek","Viktor Snytkin","Alikhan Muratuly"],
        "L": ["Dastan Sadyraliyev","Daryn Bakyrkhan","Vlad Lishanlo","Aidyn Galymbekov","Said Soltanzade","Yerik Yekibay","Assylbek Nurmagambetov","Mansur Mutayev","Raimbek Sarzhakov"],
        "goals": {"Asset Khassan":1,"Iliyas Akbergen":6,"Viktor Snytkin":1,"Daryn Bakyrkhan":1,"Vlad Lishanlo":3,"Aidyn Galymbekov":1,"Mansur Mutayev":1,"Raimbek Sarzhakov":1},
        "mvp": ["Iliyas Akbergen"]
    },
    {
        "id": 4, "score": "10:5", "W": ["Zhanibek Xenbek","Vlad Lishanlo","Daryn Bakyrkhan","Bakhtiyar Temirbayev","Yernar Bestikpayev","Said Soltanzade","Dias August","Dastan Sadyraliyev","Aidyn Galymbekov","Raimbek Sarzhakov"],
        "L": ["Adok Salimzhan","Akhmetov Dias","Mansur Mutayev","Medeu Yersain","Yerik Yekibay","Yermakhan Borankhan","Mirlan Toktoshev","Daulet Bekmolda","Viktor Snytkin","Aktan Abdullaatov"],
        "goals": {"Zhanibek Xenbek":1,"Vlad Lishanlo":4,"Bakhtiyar Temirbayev":2,"Said Soltanzade":1,"Dias August":2,"Mansur Mutayev":4,"Mirlan Toktoshev":1},
        "mvp": ["Zhanibek Xenbek", "Adok Salimzhan"]
    },
    {
        "id": 5, "score": "10:13", "W": ["Iosif Vassilenko","Akhmetov Dias","Asset Khassan","Dias Bekbosyn","Said Soltanzade","Yerik Yekibay","Dias Kaibar","Viktor Snytkin","Vlad Lishanlo","Assylbek Nurmagambetov"],
        "L": ["Dastan Sadyraliyev","Daulet Bekmolda","Yermakhan Borankhan","Niyaz Bayankulov","Aldiyar Kazbekov","Mirlan Toktoshev","Daryn Bakyrkhan","Aidyn Galymbekov","Raimbek Sarzhakov","Miras Mukanov"],
        "goals": {"Said Soltanzade":1,"Dias Kaibar":4,"Viktor Snytkin":4,"Vlad Lishanlo":2,"Assylbek Nurmagambetov":2,"Aldiyar Kazbekov":2,"Daryn Bakyrkhan":1,"Aidyn Galymbekov":2,"Raimbek Sarzhakov":1,"Miras Mukanov":3},
        "mvp": ["Dias Kaibar", "Miras Mukanov"]
    },
    {
        "id": 6, "score": "5:5", "W": [], "L": [],
        "D": ["Nurkabyl Sharipbay","Miras Mukanov","Iliyas Akbergen","Adok Salimzhan","Dias Bekbosyn","Mukhammed A Askar","Niyaz Bayankulov","Yermakhan Borankhan","Aidyn Kassym","Alikhan Muratuly", "Dias Kaibar","Daryn Bakyrkhan","Vlad Lishanlo","Ansar Tanirbay","Aldiyar Kazbekov","Mirlan Toktoshev","Asset Khassan","Almas Kaneshev","Yernar Bestikpayev","Aktan Abdullaatov"],
        "goals": {"Nurkabyl Sharipbay":4,"Miras Mukanov":1,"Vlad Lishanlo":1},
        "mvp": [] 
    },
    {
        "id": 7, "score": "6:3", 
        "W": ["Dastan Sadyraliyev", "Yernur Bauyrzhanuly", "Daryn Bakyrkhan", "Yernar Bestikpayev", "Nurken Samigullin", "Dias Bekbosyn", "Aidyn Galymbekov", "Iliyas Akbergen", "Miras Mukanov", "Nurkabyl Sharipbay", "Mirlan Toktoshev"],
        "L": ["Aidyn Kassym", "Zhanibek Xenbek", "Niyaz Bayankulov", "Asset Khassan", "Aldiyar Kazbekov", "Yeldos Ismailov", "Adok Salimzhan", "Bakhtiyar Temirbayev", "Umid Kamilov", "Vlad Lishanlo"],
        "D": [],
        "goals": {"Nurkabyl Sharipbay":3, "Miras Mukanov":1, "Mirlan Toktoshev":1, "Adok Salimzhan":1, "Vlad Lishanlo":1, "Aldiyar Kazbekov":1},
        "mvp": []
    }
]

PLAYER_PROPS = {
    "Dias Bekbosyn": {"pos": "CAM", "alt": "CM, FWD, CDM, LW, RW"},
    "Yermakhan Borankhan": {"pos": "RB", "alt": ""},
    "Medeu Yersain": {"pos": "CB", "alt": "RB"},
    "Yerik Yekibay": {"pos": "CDM", "alt": "LW"},
    "Ansar Tanirbay": {"pos": "CDM", "alt": ""},
    "Daryn Bakyrkhan": {"pos": "CM", "alt": "CB, LB, RW"},
    "Miras Mukanov": {"pos": "RW", "alt": "LW, CM, FWD"},
    "Bakhtiyar Temirbayev": {"pos": "RB", "alt": "RM, RW, LW"},
    "Akhmetov Dias": {"pos": "RB", "alt": "RM"},
    "Mukhammed A Askar": {"pos": "FWD", "alt": "LB, CDM, CM"},
    "Viktor Snytkin": {"pos": "FWD", "alt": "FWD"},
    "Aldiyar Kazbekov": {"pos": "CAM", "alt": "CM, CDM"},
    "Iliyas Akbergen": {"pos": "CM", "alt": "LM, RM, RW, LW"},
    "Adil Baizhanov": {"pos": "CB", "alt": "LB, RB, RW, LW"},
    "Vlad Lishanlo": {"pos": "LW", "alt": "LW, RW, CM, LM, RM, LB, RB"},
    "Nurkabyl Sharipbay": {"pos": "ST", "alt": "CAM, RW, LW"},
    "Dastan Sadyraliyev": {"pos": "GK", "alt": ""},
    "Rauan Tanov": {"pos": "CM", "alt": "RM, LM, LW"},
    "Adok Salimzhan": {"pos": "CM", "alt": ""},
    "Assylbek Nurmagambetov": {"pos": "FWD", "alt": "CAM, RW, LW"},
    "Dias August": {"pos": "LW", "alt": "RB, RW, FWD"},
    "Yernar Bestikpayev": {"pos": "LB", "alt": "RB, CB, RW, LW"},
    "Aidyn Kassym": {"pos": "GK", "alt": ""},
    "Niyaz Bayankulov": {"pos": "CB", "alt": "RB, LB"},
    "Mirlan Toktoshev": {"pos": "RW", "alt": "CDM, LW, CM"},
    "Dias Kaibar": {"pos": "RW", "alt": "LW"},
    "Asset Khassan": {"pos": "CB", "alt": "LB, RB"},
    "Amir Rustam": {"pos": "RB", "alt": "RW, CM"},
    "Said Soltanzade": {"pos": "CM", "alt": "LW, CB, RB, LB, FWD, RW"},
    "Iosif Vassilenko": {"pos": "RB", "alt": "RW"},
    "Almas Kaneshev": {"pos": "CB", "alt": "CM"},
    "Aktan Abdullaatov": {"pos": "RB", "alt": "GK, LB, LW"},
    "Mansur Mutayev": {"pos": "FWD", "alt": "RW, LW"},
    "Aidyn Galymbekov": {"pos": "CM", "alt": "LB, RB, RW, LW"},
    "Raimbek Sarzhakov": {"pos": "FWD", "alt": "CAM, RW, LW, CM"},
    "Nurken Samigullin": {"pos": "RB", "alt": "LB, CM"},
    "Yeldos Ismailov": {"pos": "RW", "alt": "LW"},
    "Yernur Bauyrzhanuly": {"pos": "LB", "alt": "RB"},
    "Arsen Kudaibergen": {"pos": "FWD", "alt": ""},
    "Umid Kamilov": {"pos": "CB", "alt": "RB, LB, ST"},
    "Zhanibek Xenbek": {"pos": "LB", "alt": "RB, RW, LW"},
    "Alikhan Muratuly": {"pos": "CM", "alt": ""},
    "Nurislam": {"pos": "CM", "alt": "LB"}
}

stats = {}

for name in PLAYER_PROPS:
    stats[name] = {"elo": 100, "gp":0, "g":0, "mvp":0}
for name in TELEGRAM_USERS:
    if name not in stats:
        stats[name] = {"elo": 100, "gp":0, "g":0, "mvp":0}

for g in games_raw:
    w_team = g.get("W", [])
    l_team = g.get("L", [])
    d_team = g.get("D", [])
    goals = g.get("goals", {})
    
    for p in w_team:
        if p not in stats: stats[p] = {"elo": 100, "gp":0, "g":0, "mvp":0}
        stats[p]["gp"] += 1; stats[p]["elo"] += 10; stats[p]["g"] += goals.get(p, 0)
    for p in l_team:
        if p not in stats: stats[p] = {"elo": 100, "gp":0, "g":0, "mvp":0}
        stats[p]["gp"] += 1
        if g["id"] == 1 and p in ["Arsen Kudaibergen","Aidyn Galymbekov","Umid Kamilov","Daryn Bakyrkhan","Zhanibek Xenbek","Aktan Abdullaatov"]:
            stats[p]["elo"] += 0; stats[p]["g"] += goals.get(p, 0)
        else:
            stats[p]["elo"] -= 5; stats[p]["g"] += goals.get(p, 0)
    for p in d_team:
        if p not in stats: stats[p] = {"elo": 100, "gp":0, "g":0, "mvp":0}
        stats[p]["gp"] += 1; stats[p]["elo"] += 0; stats[p]["g"] += goals.get(p, 0)

    for p in g.get("mvp", []):
        if p in stats:
            stats[p]["mvp"] += 1
            stats[p]["elo"] += 5

def name_to_user_id(name):
    """Generate deterministic pseud-random negative user_ids for seeding."""
    return -abs(hash(name)) % (10**9)

def seed_db():
    db = next(get_db())
    # Clear existing if needed, or simply merge
    db.execute(text("TRUNCATE TABLE users CASCADE;"))
    db.commit()
    print("Seeding database with Player Profiles...")

    added = 0
    # Add mapped players
    for full_name, handle in TELEGRAM_USERS.items():
        st = stats.get(full_name, {"elo": 100, "gp":0, "g":0, "mvp":0})
        props = PLAYER_PROPS.get(full_name, {"pos": "CM", "alt": ""})
        # Check mapping for fallback pos
        if full_name.lower() == "nurken samigullin":
            props = {"pos": "RB", "alt": "LB, CM"}
            
        alt_list = [x.strip() for x in props["alt"].split(',')] if props["alt"] else []
        
        user = User(
            user_id=name_to_user_id(full_name),
            username=handle,
            full_name=full_name,
            player_position=props["pos"],
            stats_matches=st["gp"],
            stats_mvp=st["mvp"],
            rating=st["elo"],
            games_played=st["gp"],
            alt_positions=alt_list
        )
        db.merge(user)
        added += 1
        
    # Also add anyone in stats not explicitly in TELEGRAM_USERS (optional, for history)
    for full_name, st in stats.items():
        if full_name not in TELEGRAM_USERS:
            props = PLAYER_PROPS.get(full_name, {"pos": "CM", "alt": ""})
            alt_list = [x.strip() for x in props["alt"].split(',')] if props["alt"] else []
            user = User(
                user_id=name_to_user_id(full_name),
                username=None,
                full_name=full_name,
                player_position=props["pos"],
                stats_matches=st["gp"],
                stats_mvp=st["mvp"],
                rating=st["elo"],
                games_played=st["gp"],
                alt_positions=alt_list
            )
            db.merge(user)
            added += 1

    db.commit()
    print(f"Successfully seeded {added} player profiles into PostgreSQL via SQLAlchemy.")

if __name__ == "__main__":
    seed_db()
