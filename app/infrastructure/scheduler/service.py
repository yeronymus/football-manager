from datetime import datetime, timedelta
from app.scheduler.main import scheduler
from app.scheduler.tasks import (
    send_voting_message, 
    remind_admin_to_finish, 
    release_gk_slots, 
    publish_game_task,
    calculate_mvp
)
from app.db.models import Game
import logging

logger = logging.getLogger(__name__)

class SchedulerService:
    """
    Infrastructure service to manage APJobScheduler tasks.
    Enforces deterministic Job IDs and centralizes scheduling logic.
    """
    
    def schedule_game_lifecycle(self, game: Game):
        """Schedules all standard tasks for a new game."""
        # 1. Publish Task (if needed)
        # Assuming publish is done immediately by Service if needed, 
        # or via this method if we pass 'publish_at'. 
        # For now, let's focus on the 'lifecycle' events: Voting, Reminder, GK Release.
        
        if not game.date_time:
             return

        self.schedule_voting(game.id, game.date_time)
        self.schedule_admin_reminder(game.id, game.date_time)
        self.schedule_gk_release(game)

    def schedule_voting(self, game_id: int, date_time: datetime):
        """Schedules voting task."""
        # Voting opens 2.5h after game start
        run_date = date_time + timedelta(hours=2, minutes=30)
        now_tz = datetime.now(date_time.tzinfo) if date_time.tzinfo else datetime.now()
        
        if run_date > now_tz:
            job_id = f"voting_{game_id}"
            scheduler.add_job(
                send_voting_message, 
                'date', 
                run_date=run_date, 
                args=[game_id], 
                id=job_id, 
                replace_existing=True
            )
            logger.info(f"Scheduled voting for game {game_id} at {run_date}")

    def schedule_admin_reminder(self, game_id: int, date_time: datetime):
        """Schedules admin reminder."""
        # Reminder 7.5h after game start (5h after voting opens)
        run_date = date_time + timedelta(hours=7, minutes=30)
        now_tz = datetime.now(date_time.tzinfo) if date_time.tzinfo else datetime.now()
        
        if run_date > now_tz:
            job_id = f"reminder_{game_id}"
            scheduler.add_job(
                remind_admin_to_finish, 
                'date', 
                run_date=run_date, 
                args=[game_id], 
                id=job_id, 
                replace_existing=True
            )
            logger.info(f"Scheduled reminder for game {game_id} at {run_date}")

    def schedule_gk_release(self, game: Game):
        """Schedules GK slot release."""
        if game.gk_hours <= 0:
            return
            
        run_date = game.created_at + timedelta(hours=game.gk_hours)
        now_tz = datetime.now(game.created_at.tzinfo) if game.created_at.tzinfo else datetime.now()
        
        if run_date > now_tz:
            job_id = f"gk_release_{game.id}"
            scheduler.add_job(
                release_gk_slots, 
                'date', 
                run_date=run_date, 
                args=[game.id], 
                id=job_id, 
                replace_existing=True
            )
            logger.info(f"Scheduled GK release for game {game.id} at {run_date}")

    def schedule_publish(self, game_id: int, publish_at: datetime):
        """Schedules delayed publishing."""
        now_tz = datetime.now(publish_at.tzinfo) if publish_at.tzinfo else datetime.now()
        
        if publish_at > now_tz:
            job_id = f"publish_{game_id}"
            scheduler.add_job(
                publish_game_task,
                'date',
                run_date=publish_at,
                args=[game_id],
                id=job_id,
                replace_existing=True
            )

    def schedule_mvp_calculation(self, game_id: int):
        """
        Schedules MVP calculation 5h after voting starts.
        Typically called by send_voting_message handler, but we expose it here
        for manual scheduling or recovery.
        """
        # Voting opens 2.5h after game. MVP calc is 5h after THAT (total 7.5h).
        # We need to know specific time.
        # Ideally, we calculate it from game_time. 
        # But this method signature only has game_id? 
        # Let's change signature or fetch game.
        # Fetching game inside infrastructure service is discouraged (circular dependency risk).
        # Better: pass date_time.
        pass

    def schedule_mvp_calculation_at(self, game_id: int, run_date: datetime):
        """Schedules MVP calculation at specific time."""
        now_tz = datetime.now(run_date.tzinfo) if run_date.tzinfo else datetime.now()
        
        if run_date > now_tz:
            job_id = f"mvp_calc_{game_id}"
            scheduler.add_job(
                calculate_mvp,
                'date',
                run_date=run_date,
                args=[game_id],
                id=job_id,
                replace_existing=True
            )
            logger.info(f"Scheduled MVP calculation for game {game_id} at {run_date}")

    def cancel_game_tasks(self, game_id: int):
        """Cancels all tasks for a game."""
        job_ids = [
            f"voting_{game_id}",
            f"reminder_{game_id}",
            f"gk_release_{game_id}",
            f"publish_{game_id}",
            f"mvp_calc_{game_id}"
        ]
        
        for job_id in job_ids:
            try:
                job = scheduler.get_job(job_id)
                if job:
                    scheduler.remove_job(job_id)
                    logger.info(f"Removed job {job_id}")
            except Exception as e:
                logger.warning(f"Failed to remove job {job_id}: {e}")
