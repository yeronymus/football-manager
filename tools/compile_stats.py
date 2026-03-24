#!/usr/bin/env python3
"""
Complete player statistics for all 5 games.
"""

# ============================================================
# GAME 1 — 2026-01-17, Sportovní centrum Prosek (3 teams)
# Score: A 13 : B 7 : C 4, Winner: A, MVP: Dias Bekbosyn
# ============================================================
GAME_1 = {
    "id": 1, "date": "17.01", "teams": {
        "A": {"result": "WIN", "players": {
            "Dias Bekbosyn": 5, "Vlad Lishanlo": 3, "Aldiyar Kazbekov": 2,
            "Miras Mukanov": 2, "Said Soltanzade": 1, "Yernur Bauyrzhanuly": 1}},
        "B": {"result": "2ND", "players": {
            "Arsen Kudaibergen": 3, "Aidyn Galymbekov": 2, "Umid Kamilov": 1,
            "Daryn Bakyrkhan": 0, "Zhanibek Xenbek": 1, "Aktan Abdullaatov": 0}},
        "C": {"result": "LOSS", "players": {
            "Alikhan Muratuly": 0, "Yeldos Ismailov": 2, "Assylbek Nurmagambetov": 0,
            "Ansar Tanirbay": 0, "Bakhtiyar Temirbayev": 1, "Raimbek Sarzhakov": 1}}
    }, "mvp": ["Dias Bekbosyn"], "score": "13:7:4"
}

# ============================================================
# GAME 2 — 2026-01-24, Plamínkové, Praha (2 teams)
# Score: A 13 : B 12, Winner: A, MVP: Nurkabyl Sharipbay
# ============================================================
GAME_2 = {
    "id": 2, "date": "24.01", "teams": {
        "A": {"result": "WIN", "players": {
            "Nurkabyl Sharipbay": 7, "Said Soltanzade": 1, "Mirlan Toktoshev": 2,
            "Daryn Bakyrkhan": 0, "Yernur Bauyrzhanuly": 0, "Aktan Abdullaatov": 0,
            "Zhanibek Xenbek": 0, "Dastan Sadyraliyev": 0, "Assylbek Nurmagambetov": 0}},
        "B": {"result": "LOSS", "players": {
            "Vlad Lishanlo": 3, "Iliyas Akbergen": 2, "Arsen Kudaibergen": 2,
            "Aidyn Galymbekov": 2, "Yeldos Ismailov": 0, "Yerik Yekibay": 0,
            "Dias Bekbosyn": 0, "Yermakhan Borankhan": 0, "Adil Baizhanov": 0}}
    }, "mvp": ["Nurkabyl Sharipbay"], "score": "13:12"
}

# ============================================================
# GAME 3 — 2026-01-31, Plamínkové, Praha (2 teams)
# Score: A 8 : B 11, Winner: B, MVP: Iliyas Akbergen
# ============================================================
GAME_3 = {
    "id": 3, "date": "31.01", "teams": {
        "A": {"result": "LOSS", "players": {
            "Dastan Sadyraliyev": 0, "Daryn Bakyrkhan": 1, "Vlad Lishanlo": 3,
            "Aidyn Galymbekov": 1, "Said Soltanzade": 0, "Yerik Yekibay": 0,
            "Assylbek Nurmagambetov": 0, "Mansur Mutayev": 1, "Raimbek Sarzhakov": 1}},
        "B": {"result": "WIN", "players": {
            "Beka": 0, "Daulet Bekmolda": 0, "Asset Khassan": 1,
            "Yermakhan Borankhan": 0, "Dias Bekbosyn": 0, "Iliyas Akbergen": 6,
            "Zhanibek Xenbek": 0, "Viktor Snytkin": 1, "Alikhan Muratuly": 0}}
    }, "mvp": ["Iliyas Akbergen"], "score": "8:11"
}

# ============================================================
# GAME 4 — 2026-02-07, Plamínkové, Praha (2 teams, 10v10)
# Score: A 10 : B 5, Winner: A
# MVP: Zhanibek Xenbek (Team A), Adok Salimzhan (Team B)
# Team assignments deduced from MVP voting + goal attribution
# ============================================================
GAME_4 = {
    "id": 4, "date": "07.02", "teams": {
        "A": {"result": "WIN", "players": {
            # Known from MVP vote for Team A + goals
            "Zhanibek Xenbek": 1, "Vlad Lishanlo": 4, "Daryn Bakyrkhan": 0,
            "Bakhtiyar Temirbayev": 2, "Yernar Bestikpayev": 0,
            "Said Soltanzade": 1, "Dias August": 2, "Mirlan Toktoshev": 0,
            # Remaining assigned to fill 10 (GK likely Team A)
            "Dastan Sadyraliyev": 0, "Aidyn Galymbekov": 0}},
        "B": {"result": "LOSS", "players": {
            # Known from MVP vote for Team B
            "Adok Salimzhan": 0, "Akhmetov Dias": 0, "Mansur Mutayev": 4,
            "Medeu Yersain": 0, "Yerik Yekibay": 0, "Yermakhan Borankhan": 0,
            "Mirlan Toktoshev": 1,
            # Remaining
            "Daulet Bekmolda": 0, "Viktor Snytkin": 0, "Aktan Abdullaatov": 0,
            "Raimbek Sarzhakov": 0}}
    }, "mvp": ["Zhanibek Xenbek", "Adok Salimzhan"], "score": "10:5"
}

# ============================================================
# GAME 5 — 2026-02-14, Plamínkové, Praha (2 teams, 10v10)  
# Score: A 10 : B 13, Winner: B
# MVP: Dias Kaibar, Miras Mukanov
# ============================================================
GAME_5 = {
    "id": 5, "date": "14.02", "teams": {
        "A": {"result": "LOSS", "players": {
            "Dastan Sadyraliyev": 0, "Daulet Bekmolda": 0, "Yermakhan Borankhan": 0,
            "Niyaz Bayankulov": 0, "Aldiyar Kazbekov": 2, "Mirlan Toktoshev": 0,
            "Daryn Bakyrkhan": 1, "Aidyn Galymbekov": 2, "Raimbek Sarzhakov": 1,
            "Miras Mukanov": 3}},
        "B": {"result": "WIN", "players": {
            "Iosif Vassilenko": 0, "Akhmetov Dias": 0, "Asset Khassan": 0,
            "Dias Bekbosyn": 0, "Said Soltanzade": 1, "Yerik Yekibay": 0,
            "Dias Kaibar": 4, "Viktor Snytkin": 4, "Vlad Lishanlo": 2,
            "Assylbek Nurmagambetov": 2}}
    }, "mvp": ["Dias Kaibar", "Miras Mukanov"], "score": "10:13"
}

ALL_GAMES = [GAME_1, GAME_2, GAME_3, GAME_4, GAME_5]

# Current roster for Game 6
CURRENT_ROSTER = [
    "Dias Bekbosyn", "Yermakhan Borankhan", "Medeu Yersain", "Yerik Yekibay",
    "Ansar Tanirbay", "Daryn Bakyrkhan", "Miras Mukanov", "Bakhtiyar Temirbayev",
    "Akhmetov Dias", "Mukhammed A Askar", "Viktor Snytkin", "Aldiyar Kazbekov",
    "Iliyas Akbergen", "Adil Baizhanov", "Vlad Lishanlo", "Nurkabyl Sharipbay",
    "Dastan Sadyraliyev", "Rauan Tanov", "Adok Salimzhan", "Assylbek Nurmagambetov",
    "Dias August", "Yernar Bestikpayev", "Aidyn Kassym", "Niyaz Bayankulov",
    "Mirlan Toktoshev", "Dias Kaibar", "Asset Khassan", "Amir Rustam",
    "Said Soltanzade", "Iosif Vassilenko", "Almas Kaneshev", "Aktan Abdullaatov",
    "Mansur Mutayev"
]

# ============================================================
# COMPILE
# ============================================================

player_stats = {}

# Initialize all known players (roster + historical)
all_players = set(CURRENT_ROSTER)
for game in ALL_GAMES:
    for team in game["teams"].values():
        for p in team["players"]:
            all_players.add(p)

for name in all_players:
    player_stats[name] = {"games": 0, "goals": 0, "wins": 0, "losses": 0, "draws": 0, "mvp": 0, "game_details": []}

for game in ALL_GAMES:
    for team_key, team in game["teams"].items():
        for player, goals in team["players"].items():
            s = player_stats[player]
            s["games"] += 1
            s["goals"] += goals
            if team["result"] == "WIN":
                s["wins"] += 1
            elif team["result"] == "LOSS":
                s["losses"] += 1
            else:
                s["draws"] += 1
            
            detail = f"G{game['id']}({game['date']}): {goals}g"
            if team["result"] == "WIN":
                detail += " ✅"
            else:
                detail += " ❌"
            s["game_details"].append(detail)
    
    for mvp_name in game["mvp"]:
        if mvp_name in player_stats:
            player_stats[mvp_name]["mvp"] += 1

# ============================================================
# PRINT
# ============================================================

print("=" * 85)
print("📊 ПОЛНАЯ СТАТИСТИКА ИГРОКОВ (Игры 1-5)")
print("=" * 85)

# Sort roster players by goals desc, then games desc
sorted_roster = sorted(CURRENT_ROSTER, key=lambda n: (-player_stats[n]["goals"], -player_stats[n]["games"], n))

print(f"\n{'#':<4} {'Игрок':<28} {'Игры':<6} {'Голы':<6} {'Поб':<5} {'Пор':<5} {'MVP':<6} {'Г/И':<6}")
print("-" * 85)

for i, name in enumerate(sorted_roster, 1):
    s = player_stats[name]
    mvp_str = f"🏅{s['mvp']}" if s["mvp"] > 0 else ""
    gpi = f"{s['goals']/s['games']:.1f}" if s["games"] > 0 else "-"
    print(f"{i:<4} {name:<28} {s['games']:<6} {s['goals']:<6} {s['wins']:<5} {s['losses']:<5} {mvp_str:<6} {gpi:<6}")

print("\n" + "=" * 85)
print("🏅 ТОП БОМБАРДИРЫ (все игроки за 5 игр)")
print("-" * 50)
all_sorted = sorted(player_stats.items(), key=lambda x: -x[1]["goals"])
for i, (name, s) in enumerate(all_sorted[:15], 1):
    if s["goals"] > 0:
        gpi = f"{s['goals']/s['games']:.1f}" if s["games"] > 0 else "-"
        in_roster = "📋" if name in CURRENT_ROSTER else ""
        print(f"  {i:>2}. {name:<28} {s['goals']:>2} голов ({s['games']} игр, {gpi} г/и) {in_roster}")

print("\n🏆 MVP НАГРАДЫ")
print("-" * 50)
for name, s in sorted(player_stats.items(), key=lambda x: -x[1]["mvp"]):
    if s["mvp"] > 0:
        print(f"  ⭐ {name}: {s['mvp']}x MVP")

print("\n📋 ИСТОРИЯ ПО ИГРОКАМ (только текущий состав)")
print("-" * 50)
for name in sorted_roster:
    s = player_stats[name]
    if s["games"] > 0:
        wr = f"{s['wins']/s['games']*100:.0f}%" if s["games"] > 0 else "0%"
        print(f"\n  {name} | {s['games']}GP {s['goals']}G {s['wins']}W {s['losses']}L | WR: {wr}")
        for d in s["game_details"]:
            print(f"    {d}")
