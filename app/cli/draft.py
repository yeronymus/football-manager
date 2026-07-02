# app/cli/draft.py
import os
import sys

# Ensure project root in path
sys.path.append(os.getcwd())

from app.core.domain.historical_data import PLAYER_PROPS, FAST_SET, GAMES_1_7

def calc_win_pct(w, d, l):
    total = w + l + d
    if total == 0: return "-"
    return f"{w/total*100:.0f}%"

async def generate_draft_report_command(args):
    """Generate Draft Report markdown file."""
    output_file = args.output or "Draft_Stats.md"
    print(f"Generating Draft Report to {output_file}...")
    
    # 1. Compile stats from historical games (for simplicity, like generate_draft.py did)
    stats = {}
    for p in PLAYER_PROPS:
        stats[p] = {"elo": 100, "gp": 0, "g": 0, "w": 0, "l": 0, "d": 0, "mvp": 0}

    for g in GAMES_1_7:
        w_team = g.get("W", [])
        l_team = g.get("L", [])
        goals = g.get("goals", {})
        
        for p in w_team:
            if p not in stats: stats[p] = {"elo":100,"gp":0,"g":0,"w":0,"l":0,"d":0,"mvp":0}
            stats[p]["gp"] += 1; stats[p]["w"] += 1; stats[p]["elo"] += 10
            stats[p]["g"] += goals.get(p, 0)
        for p in l_team:
            if p not in stats: stats[p] = {"elo":100,"gp":0,"g":0,"w":0,"l":0,"d":0,"mvp":0}
            stats[p]["gp"] += 1; stats[p]["l"] += 1
            # Simulation of draw logic for Game 1
            if g["id"] == 1 and p in ["Arsen Kudaibergen", "Aidyn Galymbekov", "Umid Kamilov", "Daryn Bakyrkhan", "Zhanibek Xenbek", "Aktan Abdullaatov"]:
                stats[p]["d"] += 1; stats[p]["l"] -= 1
            else:
                stats[p]["elo"] -= 5
            stats[p]["g"] += goals.get(p, 0)
        for p in g.get("mvp", []):
            if p in stats: stats[p]["mvp"] += 1; stats[p]["elo"] += 5

    # 2. Target Draft List (replicated from tools/generate_draft.py)
    draft_list = [
        "Yernar Bestikpayev", "Yeldos Ismailov", "Adok Salimzhan", "Yernur Bauyrzhanuly", "Bakhtiyar Temirbayev", 
        "Dias August", "Dias Bekbosyn", "Mirlan Toktoshev", "Niyaz Bayankulov", "Iliyas Akbergen", 
        "Dastan Sadyraliyev", "Aidyn Galymbekov", "Nurkabyl Sharipbay", "Raimbek Sarzhakov", "Nurken Samigullin", 
        "Vlad Lishanlo", "Aidyn Kassym", "Aldiyar Kazbekov", "Miras Mukanov", "Nurislam", 
        "Zhanibek Xenbek", "Mansur Mutayev", "Assylbek Nurmagambetov", "Daryn Bakyrkhan", "Yerik Yekibay", 
        "Umid Kamilov", "Asset Khassan", "Medeu Yersain"
    ]

    with open(output_file, "w", encoding='utf-8') as f:
        draft_stats = []
        for p in draft_list:
            if p not in stats:
                draft_stats.append((p, PLAYER_PROPS.get(p, {"pos": "?"})["pos"], 100, 0, 0, "-", 0, "☪" if p in FAST_SET else ""))
            else:
                s = stats[p]
                draft_stats.append((p, PLAYER_PROPS[p]["pos"], s["elo"], s["gp"], s["g"], calc_win_pct(s["w"], s.get("d",0), s["l"]), s["mvp"], "☪" if p in FAST_SET else ""))
                
        draft_stats.sort(key=lambda x: (-x[2], -x[4], -x[3]))
        
        f.write("| Player | Pos | ELO | Games | Goals | Win% | MVP | Fasting |\n")
        f.write("|--------|-----|-----|-------|-------|------|-----|---------|\n")
        for row in draft_stats:
            mvp_star = f"⭐{row[6]}" if row[6] > 0 else ""
            f.write(f"| {row[0]} | {row[1]} | **{row[2]}** | {row[3]} | {row[4]} | {row[5]} | {mvp_star} | {row[7]} |\n")

    print(f"DRAFT REPORT DONE: {output_file}")
