import os
import subprocess
import datetime
from datetime import timezone
from sqlalchemy import text, select, delete

from app.db.database import async_session_maker
from app.db.models import Game, Signup, GameStats, Team, GameStatus, User, Chat, SignupStatus, RatingHistory
from app.core.domain.historical_data import GAMES_1_7
from sqlalchemy.dialects.postgresql import insert

async def seed_chats_command(args):
    """Seed configured initial chats into the database via Upsert."""
    from app.config import settings
    if not settings.initial_chats:
        print("No initial_chats configured in .env")
        return

    async with async_session_maker() as db:
        print(f"Upserting {len(settings.initial_chats)} defined chats...")
        
        chats_to_upsert = []
        for chat_data in settings.initial_chats:
            chat_id = chat_data.get("id")
            title = chat_data.get("title", "")
            if chat_id is not None:
                chats_to_upsert.append({"chat_id": chat_id, "title": title})
                
        if chats_to_upsert:
            stmt = insert(Chat)
            stmt = stmt.on_conflict_do_update(
                index_elements=['chat_id'],
                set_={
                    'title': stmt.excluded.title
                }
            )
            await db.execute(stmt, chats_to_upsert)
        
        await db.commit()
        print("Chats seeding completed successfully.")

async def seed_history_command(args):
    """Seed historical games (1-7) into the database."""
    async with async_session_maker() as db:
        try:
async def _ensure_archive_chat(db, archive_chat_id):
    chat_res = await db.execute(select(Chat).where(Chat.chat_id == archive_chat_id))
    chat = chat_res.scalar_one_or_none()
    if not chat:
        chat = Chat(chat_id=archive_chat_id, title="Archive History")
        db.add(chat)
        await db.commit()

def _parse_and_create_game_obj(g_data, archive_chat_id, creator_id):
    score_parts = g_data['score'].split(':')
    s_a = int(score_parts[0])
    s_b = int(score_parts[1])
    s_c = int(score_parts[2]) if len(score_parts) > 2 else 0
    dt = datetime.datetime.strptime(g_data['date'], "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=10, minute=0)
    w_list = g_data.get('W', [])
    winner_team = Team.A if w_list else None
    return Game(
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

def _add_players_to_session(db, game_id, names, team, user_map, mvp_list, goals_map):
    added = 0
    for name in names:
        clean_name = name.strip().lower()
        if clean_name in user_map:
            u = user_map[clean_name]
            db.add(Signup(game_id=game_id, user_id=u.user_id, status=SignupStatus.ACTIVE, team=team))
            db.add(GameStats(game_id=game_id, user_id=u.user_id, goals=goals_map.get(name, 0), is_mvp=(name in mvp_list)))
            added += 1
        else:
            print(f"  WARNING: User '{name}' not found in DB.")
    return added

async def seed_history_command(args):
    """Seed historical games (1-7) into the database."""
    async with async_session_maker() as db:
        try:
            print("Cleaning up match history...")
            await db.execute(text("TRUNCATE TABLE game_stats, signups, rating_history, games RESTART IDENTITY CASCADE"))
            await db.commit()

            archive_chat_id = -1000000000001
            await _ensure_archive_chat(db, archive_chat_id)

            users_res = await db.execute(select(User))
            users = users_res.scalars().all()
            user_map = {u.full_name.strip().lower(): u for u in users}
            print(f"Mapped {len(user_map)} users from DB.")

            if not users:
                print("ERROR: No users in database. Seed users first.")
                return

            creator_id = users[0].user_id
            games_to_create = []

            for g_data in GAMES_1_7:
                game = _parse_and_create_game_obj(g_data, archive_chat_id, creator_id)
                db.add(game)
                games_to_create.append((game, g_data))

            await db.flush()

            for game, g_data in games_to_create:
                mvp_list = g_data.get('mvp', [])
                goals_map = g_data.get('goals', {})
                w_list = g_data.get('W', [])
                l_list = g_data.get('L', [])
                d_list = g_data.get('D', [])

                cnt = 0
                cnt += _add_players_to_session(db, game.id, w_list, Team.A, user_map, mvp_list, goals_map)
                cnt += _add_players_to_session(db, game.id, l_list, Team.B, user_map, mvp_list, goals_map)
                cnt += _add_players_to_session(db, game.id, d_list, Team.A, user_map, mvp_list, goals_map)
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

async def backup_db_command(args):
    """Create a database backup using pg_dump."""
    from app.config import settings
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.sql"
    
    print(f"Creating backup: {filename}...")
    
    # Set PGPASSWORD environment variable for pg_dump
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.postgres_password
    
    cmd = [
        "pg_dump",
        "-h", settings.postgres_host,
        "-p", str(settings.postgres_port),
        "-U", settings.postgres_user,
        "-d", settings.postgres_db,
        "-f", filename
    ]
    
    try:
        # Note: pg_dump must be installed (added to Dockerfile)
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Backup created successfully: {filename}")
        else:
            print(f"Error creating backup: {result.stderr}")
    except FileNotFoundError:
        print("ERROR: pg_dump not found. Ensure postgresql-client is installed.")
    except Exception as e:
        print(f"Failed to run pg_dump: {e}")
