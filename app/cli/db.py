# app/cli/db.py
import asyncio
import datetime
from datetime import timezone
from sqlalchemy import text, select, delete

from app.db.database import async_session_maker
from app.db.models import Game, Signup, GameStats, Team, GameStatus, User, Chat, SignupStatus, RatingHistory
from app.core.domain.historical_data import GAMES_1_7

async def seed_history_command(args):
    """Seed historical games (1-7) into the database."""
    async with async_session_maker() as db:
        try:
            print("Cleaning up match history...")
            await db.execute(text("TRUNCATE TABLE game_stats, signups, rating_history, games RESTART IDENTITY CASCADE"))
            await db.commit()

            # Ensure archive chat exists
            archive_chat_id = -1000000000001
            chat_res = await db.execute(select(Chat).where(Chat.chat_id == archive_chat_id))
            chat = chat_res.scalar_one_or_none()
            if not chat:
                chat = Chat(chat_id=archive_chat_id, title="Archive History")
                db.add(chat)
                await db.commit()

            # Build user map
            users_res = await db.execute(select(User))
            users = users_res.scalars().all()
            user_map = {u.full_name.strip().lower(): u for u in users}
            print(f"Mapped {len(user_map)} users from DB.")

            if not users:
                print("ERROR: No users in database. Seed users first.")
                return

            creator_id = users[0].user_id

            for g_data in GAMES_1_7:
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
                db.add(game)
                await db.flush()
                
                mvp_list = g_data.get('mvp', [])
                goals_map = g_data.get('goals', {})
                
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
                            db.add(signup)
                            # Stats
                            stat = GameStats(
                                game_id=game.id,
                                user_id=u.user_id,
                                goals=goals_map.get(name, 0),
                                is_mvp=(name in mvp_list)
                            )
                            db.add(stat)
                            added += 1
                        else:
                            print(f"  WARNING: User '{name}' not found in DB.")
                    return added

                cnt = 0
                cnt += await add_players(w_list, Team.A)
                cnt += await add_players(l_list, Team.B)
                cnt += await add_players(d_list, Team.A) # Draws on A
                print(f"Game {g_data['id']}: Added {cnt} players.")
                
            await db.commit()
            print("IMPORT COMPLETED SUCCESSFULLY")
        except Exception as e:
            print(f"ERROR: {e}")
            await db.rollback()
            import traceback
            traceback.print_exc()

async def reset_db_command(args):
    """Reset all user ratings and counters."""
    async with async_session_maker() as db:
        print("Resetting all users to 100 ELO, 0 games...")
        await db.execute(text("UPDATE users SET rating=100, games_played=0, stats_mvp=0, stats_matches=0"))
        print("Clearing rating history...")
        await db.execute(delete(RatingHistory))
        await db.commit()
        print("Database reset complete.")
