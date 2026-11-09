from datetime import datetime, timedelta
from app.scheduler.main import scheduler
from app.scheduler.tasks import (
    send_voting_message, 
    release_gk_slots, 
    publish_game_task,
    calculate_mvp,
    send_pre_game_reminder_task,
    check_inventory_alerts_task,
    check_unopened_voting_task,
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
        if not game.date_time:
            return

        duration = getattr(game, 'duration', 2.0) or 2.0
        self.schedule_voting(game.id, game.date_time, duration=duration)
        self.schedule_gk_release(game)
        self.schedule_pre_game_reminder(game.id, game.date_time)

    def schedule_pre_game_reminder(self, game_id: int, date_time: datetime):
        """Schedules pre-match reminder 3 hours before kickoff."""
        run_date = date_time - timedelta(hours=3)
        now_tz = datetime.now(date_time.tzinfo) if date_time.tzinfo else datetime.now()
        if run_date > now_tz:
            job_id = f"reminder_t3h_{game_id}"
            scheduler.add_job(
                send_pre_game_reminder_task,
                'date',
                run_date=run_date,
                args=[game_id],
                id=job_id,
                replace_existing=True
            )
            logger.info(f"Scheduled T-3h pre-match reminder for game {game_id} at {run_date}")

    def schedule_voting(self, game_id: int, date_time: datetime, duration: float = 2.0):
        """Schedules voting task 2 hours after kickoff (allowing ~30m cooldown/locker-room time after a 1.5h match), and MVP resolution 24h later."""
        voting_hours = max(float(duration) if duration and duration > 0 else 2.0, 2.0)
        run_date = date_time + timedelta(hours=voting_hours)
        now_tz = datetime.now(date_time.tzinfo) if date_time.tzinfo else datetime.now()
        
        job_id = f"voting_{game_id}"
        if run_date > now_tz:
            scheduler.add_job(
                send_voting_message, 
                'date', 
                run_date=run_date, 
                args=[game_id], 
                id=job_id, 
                misfire_grace_time=7200,
                replace_existing=True
            )
            logger.info(f"Scheduled voting for game {game_id} at {run_date}")
        else:
            scheduler.add_job(
                send_voting_message,
                'date',
                run_date=now_tz + timedelta(seconds=2),
                args=[game_id],
                id=job_id,
                misfire_grace_time=7200,
                replace_existing=True
            )
            logger.info(f"Game {game_id} duration already elapsed; triggered immediate voting")

        # Schedule automatic MVP calculation 24 hours after voting starts
        base_calc_time = max(run_date, now_tz)
        mvp_run_date = base_calc_time + timedelta(hours=24)
        self.schedule_mvp_calculation_at(game_id, mvp_run_date)

    def schedule_periodic_unopened_voting_check(self):
        """Schedules a recurring safety check every 5 minutes for matches whose voting hasn't opened."""
        scheduler.add_job(
            check_unopened_voting_task,
            'interval',
            minutes=5,
            id="check_unopened_voting",
            misfire_grace_time=300,
            replace_existing=True
        )

    def schedule_gk_release(self, game: Game):
        """Schedules GK slot release."""
        if game.gk_hours <= 0:
            return
            
        created_at = game.created_at
        if not created_at:
            import zoneinfo
            try:
                prague_tz = zoneinfo.ZoneInfo("Europe/Prague")
                created_at = datetime.now(prague_tz)
            except Exception:
                created_at = datetime.now()
            
        run_date = created_at + timedelta(hours=game.gk_hours)
        now_tz = datetime.now(created_at.tzinfo) if created_at.tzinfo else datetime.now()
        
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
            f"gk_release_{game_id}",
            f"publish_{game_id}",
            f"mvp_calc_{game_id}",
            f"reminder_t3h_{game_id}"
        ]
        
        for job_id in job_ids:
            try:
                job = scheduler.get_job(job_id)
                if job:
                    scheduler.remove_job(job_id)
                    logger.info(f"Removed job {job_id}")
            except Exception as e:
                logger.warning(f"Failed to remove job {job_id}: {e}")
