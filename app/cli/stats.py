async def recalculate_stats_command(dry_run: bool = True):
    """Recalculate all ratings from scratch based on finished games."""
    async with async_session_maker() as s:
        print("=" * 70)
        print(f"📊 {'DRY RUN — ' if dry_run else ''}Recalculating all ratings")
        print("=" * 70)

        # 1. Reset all users
        if not dry_run:
            print("\n🔄 Resetting all users to 100 ELO...")
            from sqlalchemy import text, delete
            from app.db.models import RatingHistory
            await s.execute(text("UPDATE users SET rating=100, games_played=0, stats_mvp=0, stats_matches=0"))
            await s.execute(delete(RatingHistory))

        # 2. Get all finished games in order
        from sqlalchemy import select
        from app.db.models import GameStatus, Team, SignupStatus
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

            # Calculate team points
            team_points = {}
            if game.team_count == 2:
                sa, sb = game.score_a or 0, game.score_b or 0
                if sa == sb:
                    team_points[Team.A], team_points[Team.B] = 0, 0
                elif game.winner_team == Team.A:
                    team_points[Team.A], team_points[Team.B] = 10, -5
                elif game.winner_team == Team.B:
                    team_points[Team.A], team_points[Team.B] = -5, 10
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

            # Get MVPs and Players
            p_res = await s.execute(
                select(User, Signup.team)
                .join(Signup)
                .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
            )
            players_data = p_res.all()
            
            mvp_res = await s.execute(
                select(GameStats).where(GameStats.game_id == game.id, GameStats.is_mvp == True)
            )
            mvp_ids = set(m.user_id for m in mvp_res.scalars().all())

            for user, team in players_data:
                old_rating = user.rating
                base = team_points.get(team, 0)
                is_mvp = user.user_id in mvp_ids
                change = base + (5 if is_mvp else 0)

                print(f"    {user.full_name:<28} {old_rating} → {old_rating + change} " + ("⭐" if is_mvp else ""))
                
                if not dry_run:
                    from app.db.models import RatingHistory
                    user.rating += change
                    user.games_played += 1
                    user.stats_matches += 1
                    if is_mvp: user.stats_mvp += 1
                    s.add(RatingHistory(user_id=user.user_id, game_id=game.id, old_rating=old_rating, new_rating=user.rating, change=change))

        if not dry_run:
            await s.commit()
            print("\n✨ RECALCULATION COMPLETE!")
        else:
            print("\n🔍 DRY RUN FINISHED (No changes made)")

async def export_stats_csv_command(output_file: str = "FM_Player_Stats.csv"):
    """Export current player stats to CSV."""
    import csv
    async with async_session_maker() as s:
        from sqlalchemy import select
        res = await s.execute(select(User).order_by(User.rating.desc()))
        users = res.scalars().all()
        
        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["#", "Игрок", "ELO", "Игры", "MVP", "Г/И", "Ораза"])
            for i, u in enumerate(users, 1):
                fasting = "Да" if u.full_name in FAST_SET else ""
                gpi = f"{u.stats_matches/u.games_played:.1f}" if u.games_played > 0 else "-" # This is actually just a placeholder for goals
                writer.writerow([i, u.full_name, u.rating, u.games_played, u.stats_mvp, "-", fasting])
        print(f"Stats exported to {output_file}")

async def generate_stats_command(max_game_id: int, output_file: str = "FM_Player_Stats.xlsx"):
    """Consolidated command to generate Excel stats."""
    print(f"Generating stats up to Game #{max_game_id}...")
    
    # 1. Initialize stats from Historical Data
    stats = {}
    for p in PLAYER_PROPS:
        stats[p] = {"elo": 100, "gp": 0, "g": 0, "w": 0, "l": 0, "d": 0, "mvp": 0, "logs": [""] * max_game_id}

    # 2. Process Historical Games 1-7
    for g in GAMES_1_7:
        if g["id"] > max_game_id: break
        idx = g["id"] - 1
        w_team = g.get("W", [])
        l_team = g.get("L", [])
        d_team = g.get("D", [])
        goals = g.get("goals", {})
        
        def update_p(names, team_res, elo_ch, g_idx):
            for p in names:
                if p not in stats: stats[p] = {"elo":100,"gp":0,"g":0,"w":0,"l":0,"d":0,"mvp":0,"logs":[""]*max_game_id}
                s = stats[p]
                s["gp"] += 1
                if team_res == "W": s["w"] += 1
                elif team_res == "L": s["l"] += 1
                else: s["d"] += 1
                s["elo"] += elo_ch
                pg = goals.get(p, 0)
                s["g"] += pg
                s["logs"][g_idx] = f"{pg}g {team_res}"

        # Game 1 special case logic
        if g["id"] == 1:
            update_p(w_team, "W", 10, idx)
            draw_players = ["Arsen Kudaibergen", "Aidyn Galymbekov", "Umid Kamilov", "Daryn Bakyrkhan", "Zhanibek Xenbek", "Aktan Abdullaatov"]
            remaining_l = [p for p in l_team if p not in draw_players]
            update_p(draw_players, "D", 0, idx)
            update_p(remaining_l, "L", -5, idx)
        else:
            update_p(w_team, "W", 10, idx)
            update_p(l_team, "L", -5, idx)
            update_p(d_team, "D", 0, idx)

        for p in g.get("mvp", []):
            if p in stats: stats[p]["mvp"] += 1; stats[p]["elo"] += 5

    # 4. Excel Generation
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Player Stats {max_game_id}G"

    headers = ["#", "Группа", "Игрок", "Поз", "Альт. позиции", "ELO", "Игры", "Голы", "Победы", "Пораж.", "Win%", "MVP", "Г/И", "Ораза"]
    for i in range(1, max_game_id + 1): headers.append(f"G{i}")

    for col, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=col, value=h)
        c.font = HFont; c.fill = HF; c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); c.border = B
    
    all_players = sorted(stats.keys(), key=lambda p: (-stats[p]["elo"], -stats[p]["g"], -stats[p]["gp"]))
    SECTIONS = [("ВРАТАРИ", []), ("ЗАЩИТА", []), ("ПОЛУЗАЩИТА", []), ("НАПАДЕНИЕ", []), ("БЕЗ СТАТЫ", [])]
    
    for p in all_players:
        st = stats[p]
        props = PLAYER_PROPS.get(p, {"pos": "CM", "alt": ""})
        grp = POS_GRP.get(props["pos"], "МИД")
        gpi = f"{st['g']/st['gp']:.1f}" if st['gp'] > 0 else "-"
        d_tuple = (p, props["pos"], props.get("alt", ""), grp, st["elo"], st["gp"], st["g"], st["w"], st["l"], calc_win_pct(st['w'], st['d'], st['l']), st["mvp"], gpi, "Да" if p in FAST_SET else "", st["logs"])
        
        target = 4 if st["gp"] == 0 else (0 if grp == "ВРТ" else (1 if grp == "ЗАЩ" else (2 if grp == "МИД" else 3)))
        SECTIONS[target][1].append(d_tuple)

    row_idx = 2; num = 1
    for name, players in SECTIONS:
        if not players: continue
        for col in range(1, len(headers) + 1):
            c = ws.cell(row=row_idx, column=col); c.fill = SECT; c.border = B
        ws.cell(row=row_idx, column=2, value=name).font = SECT_FNT
        row_idx += 1
        for d in players:
            vals = [num, d[3], d[0], d[1], d[2], d[4], d[5], d[6], d[7], d[8], d[9], d[10], d[11], d[12]] + d[13]
            for col, v in enumerate(vals, 1):
                c = ws.cell(row=row_idx, column=col, value=v); c.border = B; c.alignment = Alignment(horizontal="center")
            if d[10]: ws.cell(row=row_idx, column=12).fill = GOLD
            if d[12]: ws.cell(row=row_idx, column=14).fill = FAST
            row_idx += 1; num += 1

    wb.save(output_file)
    print(f"Excel saved to {output_file}")
