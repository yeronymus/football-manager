#!/usr/bin/env python3
"""Generate CSV stats for all players across 5 games."""
import csv
import os

# ============================================================
# GAME DATA
# ============================================================
# Format: {player: goals} per team, result = W/L/D

games = [
    {"id":1,"date":"17.01","score":"13:7:4","mvp":["Dias Bekbosyn"],
     "teams":[
         {"result":"W","players":{"Dias Bekbosyn":5,"Vlad Lishanlo":3,"Aldiyar Kazbekov":2,"Miras Mukanov":2,"Said Soltanzade":1,"Yernur Bauyrzhanuly":1}},
         {"result":"D","players":{"Arsen Kudaibergen":3,"Aidyn Galymbekov":2,"Umid Kamilov":1,"Daryn Bakyrkhan":0,"Zhanibek Xenbek":1,"Aktan Abdullaatov":0}},
         {"result":"L","players":{"Alikhan Muratuly":0,"Yeldos Ismailov":2,"Assylbek Nurmagambetov":0,"Ansar Tanirbay":0,"Bakhtiyar Temirbayev":1,"Raimbek Sarzhakov":1}}
     ]},
    {"id":2,"date":"24.01","score":"13:12","mvp":["Nurkabyl Sharipbay"],
     "teams":[
         {"result":"W","players":{"Nurkabyl Sharipbay":7,"Said Soltanzade":1,"Mirlan Toktoshev":2,"Daryn Bakyrkhan":0,"Yernur Bauyrzhanuly":0,"Aktan Abdullaatov":0,"Zhanibek Xenbek":0,"Dastan Sadyraliyev":0,"Assylbek Nurmagambetov":0}},
         {"result":"L","players":{"Vlad Lishanlo":3,"Iliyas Akbergen":2,"Arsen Kudaibergen":2,"Aidyn Galymbekov":2,"Yeldos Ismailov":0,"Yerik Yekibay":0,"Dias Bekbosyn":0,"Yermakhan Borankhan":0,"Adil Baizhanov":0}}
     ]},
    {"id":3,"date":"31.01","score":"8:11","mvp":["Iliyas Akbergen"],
     "teams":[
         {"result":"L","players":{"Dastan Sadyraliyev":0,"Daryn Bakyrkhan":1,"Vlad Lishanlo":3,"Aidyn Galymbekov":1,"Said Soltanzade":0,"Yerik Yekibay":0,"Assylbek Nurmagambetov":0,"Mansur Mutayev":1,"Raimbek Sarzhakov":1}},
         {"result":"W","players":{"Beka":0,"Daulet Bekmolda":0,"Asset Khassan":1,"Yermakhan Borankhan":0,"Dias Bekbosyn":0,"Iliyas Akbergen":6,"Zhanibek Xenbek":0,"Viktor Snytkin":1,"Alikhan Muratuly":0}}
     ]},
    {"id":4,"date":"07.02","score":"10:5","mvp":["Zhanibek Xenbek","Adok Salimzhan"],
     "teams":[
         {"result":"W","players":{"Zhanibek Xenbek":1,"Vlad Lishanlo":4,"Daryn Bakyrkhan":0,"Bakhtiyar Temirbayev":2,"Yernar Bestikpayev":0,"Said Soltanzade":1,"Dias August":2,"Dastan Sadyraliyev":0,"Aidyn Galymbekov":0,"Raimbek Sarzhakov":0}},
         {"result":"L","players":{"Adok Salimzhan":0,"Akhmetov Dias":0,"Mansur Mutayev":4,"Medeu Yersain":0,"Yerik Yekibay":0,"Yermakhan Borankhan":0,"Mirlan Toktoshev":1,"Daulet Bekmolda":0,"Viktor Snytkin":0,"Aktan Abdullaatov":0}}
     ]},
    {"id":5,"date":"14.02","score":"10:13","mvp":["Dias Kaibar","Miras Mukanov"],
     "teams":[
         {"result":"L","players":{"Dastan Sadyraliyev":0,"Daulet Bekmolda":0,"Yermakhan Borankhan":0,"Niyaz Bayankulov":0,"Aldiyar Kazbekov":2,"Mirlan Toktoshev":0,"Daryn Bakyrkhan":1,"Aidyn Galymbekov":2,"Raimbek Sarzhakov":1,"Miras Mukanov":3}},
         {"result":"W","players":{"Iosif Vassilenko":0,"Akhmetov Dias":0,"Asset Khassan":0,"Dias Bekbosyn":0,"Said Soltanzade":1,"Yerik Yekibay":0,"Dias Kaibar":4,"Viktor Snytkin":4,"Vlad Lishanlo":2,"Assylbek Nurmagambetov":2}}
     ]}
]

ROSTER = [
    "Dias Bekbosyn","Yermakhan Borankhan","Medeu Yersain","Yerik Yekibay",
    "Ansar Tanirbay","Daryn Bakyrkhan","Miras Mukanov","Bakhtiyar Temirbayev",
    "Akhmetov Dias","Mukhammed A Askar","Viktor Snytkin","Aldiyar Kazbekov",
    "Iliyas Akbergen","Adil Baizhanov","Vlad Lishanlo","Nurkabyl Sharipbay",
    "Dastan Sadyraliyev","Rauan Tanov","Adok Salimzhan","Assylbek Nurmagambetov",
    "Dias August","Yernar Bestikpayev","Aidyn Kassym","Niyaz Bayankulov",
    "Mirlan Toktoshev","Dias Kaibar","Asset Khassan","Amir Rustam",
    "Said Soltanzade","Iosif Vassilenko","Almas Kaneshev","Aktan Abdullaatov",
    "Mansur Mutayev"
]

FASTING = {
    "Yernar Bestikpayev","Akhmetov Dias","Bakhtiyar Temirbayev",
    "Niyaz Bayankulov","Daulet Bekmolda","Dias August","Adok Salimzhan",
    "Ansar Tanirbay","Arsen Kudaibergen","Medeu Yersain",
    "Yermakhan Borankhan","Daryn Bakyrkhan","Mukhammed A Askar",
    "Nurkabyl Sharipbay","Nurken Samigullin","Asset Khassan",
    "Mirlan Toktoshev","Yeldos Ismailov","Amir Rustam",
    "Zhanibek Xenbek","Dias Bekbosyn"
}

# Compile
stats = {}
for p in ROSTER:
    stats[p] = {"gp":0,"g":0,"w":0,"l":0,"mvp":0,"g1":"","g2":"","g3":"","g4":"","g5":""}

for game in games:
    gk = "g" + str(game["id"])
    for team in game["teams"]:
        for player, goals in team["players"].items():
            if player not in stats:
                stats[player] = {"gp":0,"g":0,"w":0,"l":0,"mvp":0,"g1":"","g2":"","g3":"","g4":"","g5":""}
            s = stats[player]
            s["gp"] += 1
            s["g"] += goals
            if team["result"] == "W":
                s["w"] += 1
            elif team["result"] == "L":
                s["l"] += 1
            s[gk] = str(goals) + "g " + team["result"]
    for mvp in game["mvp"]:
        if mvp in stats:
            stats[mvp]["mvp"] += 1

# Sort
sorted_r = sorted(ROSTER, key=lambda n: (-stats[n]["g"], -stats[n]["gp"], n))

# Write CSV
out = "/home/yeronym/Documents/fmBot/football-manager/FM_Player_Stats.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["#","Игрок","Игры","Голы","Победы","Поражения","Win%","MVP","Голов/Игра","Ораза",
                "Игра 1 (17.01)","Игра 2 (24.01)","Игра 3 (31.01)","Игра 4 (07.02)","Игра 5 (14.02)"])
    for i, name in enumerate(sorted_r, 1):
        s = stats[name]
        wr = f"{s['w']/s['gp']*100:.0f}%" if s["gp"] > 0 else "-"
        gpi = f"{s['g']/s['gp']:.1f}" if s["gp"] > 0 else "-"
        fasting = "Да" if name in FASTING else ""
        w.writerow([i, name, s["gp"], s["g"], s["w"], s["l"], wr,
                     s["mvp"] if s["mvp"]>0 else "", gpi, fasting,
                     s["g1"], s["g2"], s["g3"], s["g4"], s["g5"]])

with open("/tmp/csv_done.txt", "w") as f:
    f.write(f"DONE: {out}")
