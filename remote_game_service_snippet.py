        """
        from app.bot.elo import calculate_new_rating
        
        # Fetch game
        game = await self.get_game(data.game_id)
        if not game:
             raise ValueError("Game not found")
        
        # Update game score and status
        if game.status == GameStatus.FINISHED:
            # Rollback previous results to allow editing/correction
            
            # 1. Revert Ratings & Games Played
            history_result = await self.session.execute(select(RatingHistory).where(RatingHistory.game_id == game.id))
            histories = history_result.scalars().all()
            for h in histories:
                user = await self.session.get(User, h.user_id)
                if user and h.old_rating is not None:
                    # We revert to old_rating. 
                    # Note: If multiple updates happened, order matters? 
                    # If we delete ALL history for this game, we effectively revert the chain steps.
                    # E.g. 100->105 (H1), 105->110 (H2).
                    # Loop H2: user=105. Loop H1: user=100. Correct.
                    user.rating = h.old_rating
                    user.games_played = max(0, user.games_played - 1)
                await self.session.delete(h)
                
            # 2. Revert Stats (MVP)
            stats_result = await self.session.execute(select(GameStats).where(GameStats.game_id == game.id))
            stats = stats_result.scalars().all()
            for s in stats:
                if s.is_mvp:
                    user = await self.session.get(User, s.user_id)
                    if user:
                        user.stats_mvp = max(0, user.stats_mvp - 1)
                await self.session.delete(s)
            
            await self.session.flush()

        # Update scores and status
        game.score_a = data.score_a
        game.score_b = data.score_b
        game.winner_team = data.winner_team
        game.status = GameStatus.FINISHED

        # MVP Logic: Driven ONLY by Manual Input (data.mvp_user_id)
        # Voting is advisory and announced in chat separately.
        mvp_ids = set()
        if data.mvp_user_id:
            mvp_ids.add(data.mvp_user_id)
        if data.mvp_team_a:
            mvp_ids.add(data.mvp_team_a)
        if data.mvp_team_b:
            mvp_ids.add(data.mvp_team_b)

        # Save player stats
        processed_stats_ids = set()
        for p_stat in data.player_stats:
            is_mvp = (p_stat.user_id in mvp_ids)
            if p_stat.goals > 0 or is_mvp:
                stat = GameStats(
                    game_id=game.id, 
                    user_id=p_stat.user_id, 
                    goals=p_stat.goals,
                    is_mvp=is_mvp
                )
                self.session.add(stat)
                processed_stats_ids.add(p_stat.user_id)
                
                # Update User Total MVP count
                if is_mvp:
                    user_obj = await self.session.get(User, p_stat.user_id)
                    if user_obj:
                         user_obj.stats_mvp += 1
        
        # Ensure MVPs without goals are recorded
        for mid in mvp_ids:
            if mid not in processed_stats_ids:
                stat = GameStats(game_id=game.id, user_id=mid, goals=0, is_mvp=True)
                self.session.add(stat)
                user_obj = await self.session.get(User, mid)
                if user_obj:
                     user_obj.stats_mvp += 1

        # ELO Calculation
        # Determine Ranks for 3-team games
        ranking = []
        if game.team_count == 3:
            scores = [
                (Team.A, game.score_a or 0),
                (Team.B, game.score_b or 0),
                (Team.C, game.score_c or 0)
            ]
            scores.sort(key=lambda x: x[1], reverse=True)
            ranking = [s[0] for s in scores] # [1st, 2nd, 3rd]

        # Fetch all active players with their teams
        result = await self.session.execute(
            select(User, Signup.team)
            .join(Signup)
            .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
        )
        players_data = result.all() # List of (User, Team)
        
        from app.db.models import RatingHistory

        for user, team in players_data:
            old_rating = user.rating
            change = -5 # Default
            
            if game.team_count == 2:
                if team == game.winner_team:
                    change = 10
                else:
                    change = -5
            else:
                # 3 Teams logic: 1st:+10, 2nd:0, 3rd:-5
                if team == ranking[0]:
                    change = 10
                elif team == ranking[1]:
                    change = 0
                else:
                    change = -5
            
            is_mvp = (user.user_id in mvp_ids)
            if is_mvp:
                change += 5
            
            user.rating += change
            user.games_played += 1
            user.stats_matches += 1
            
            # Record History
            self.session.add(RatingHistory(
                user_id=user.user_id,
                game_id=game.id,
                old_rating=old_rating,
                new_rating=user.rating,
                change=change
            ))

        await self.session.commit()
        
        # Notify chat
        from app.config import settings
        text = f"🏁 <b>Матч завершен!</b>\n\n"
        text += f"Команда оранжевые 🟠 {game.score_a}:{game.score_b} 🟢 Команда зеленые\n"
        
        # MVP
        if mvp_ids:
             text += "🌟 <b>MVP:</b> "
             mvp_names = []
             for mid in mvp_ids:
                 u = await self.session.get(User, mid)
                 if u: mvp_names.append(u.full_name)
             text += ", ".join(mvp_names) + "\n"
        
        # Show goal scorers
        scorers = [p for p in data.player_stats if p.goals > 0]
        if scorers:
            text += "\n⚽ <b>Голы:</b>\n"
            scorer_ids = [s.user_id for s in scorers]
            # Fetch names
            result = await self.session.execute(select(User).where(User.user_id.in_(scorer_ids)))
            users_map = {u.user_id: u.full_name for u in result.scalars().all()}
            
            for s in scorers:
                name = users_map.get(s.user_id, "Неизвестный")
                text += f"- {name}: {s.goals}\n"

        from app.bot.main import bot
        
        if game.message_id:
            await bot.send_message(chat_id=game.chat_id, text=text)
        else:
             logger.info(f"Silent finish for {game.id}")
