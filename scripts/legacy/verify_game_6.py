import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from sqlalchemy import select

# Add app to path
sys.path.append(os.getcwd())

from app.db.database import async_session_maker
from app.core.uow import UnitOfWork
from app.infrastructure.scheduler.service import SchedulerService
from app.core.services.stats import StatsService
from app.core.services.game_lifecycle import GameLifecycleService
from app.core.services.roster import RosterService
from app.api.schemas import GameCreate, GameUpdate, GameFinishRequest, PlayerStat
from app.db.models import User, Position, Team, Game, GameStatus

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock Scheduler to avoid actual job scheduling during test
class MockScheduler(SchedulerService):
    def schedule_game_lifecycle(self, game):
        logger.info(f"[MOCK] Scheduling lifecycle for Game {game.id}")
    def schedule_publish(self, game_id, run_date):
        logger.info(f"[MOCK] Scheduling publish for Game {game_id} at {run_date}")
    def cancel_game_tasks(self, game_id):
        logger.info(f"[MOCK] Cancelling tasks for Game {game_id}")

async def run_verification():
    logger.info("Starting Game 6 Lifecycle Verification (Rollback Mode)...")
    
    async with async_session_maker() as session:
        # Start Transaction (will rollback at end)
        async with session.begin():
            
            # 0. Setup Dependencies
            # We mock UOW to share OUR session which we control the rollback for
            # But UOW creates its own session usually. 
            # We need to inject our session into UOW or Services directly.
            # The Services take UOW. UOW takes session_factory.
            # Let's manually assemble services with THIS session for the test.
            
            # Mock UOW that uses OUR active session
            class TestUOW(UnitOfWork):
                def __init__(self, external_session):
                    self._session = external_session
                    from app.core.repositories.game_repo import GameRepository
                    from app.core.repositories.user_repository import UserRepository
                    self.game_repo = GameRepository(self._session)
                    self.user_repo = UserRepository(self._session)
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass # Do nothing, external commits/rollbacks
                async def commit(self):
                    logger.info("[TEST] UOW Commit called (Ignored in Rollback Mode)")
                    await self.session.flush() # Flush to get IDs but don't commit
            
            uow = TestUOW(session)
            scheduler = MockScheduler()
            stats_service = StatsService(session) # Takes session directly? Yes
            lifecycle_service = GameLifecycleService(uow, scheduler, stats_service)
            roster_service = RosterService(uow)
            
            # --- STEP 1: Create Game ---
            logger.info("\n--- STEP 1: Create Game ---")
            game_data = GameCreate(
                chat_id=-100123456789, # Dummy
                date_time=datetime.now() + timedelta(days=1),
                location="Test Arena",
                max_players=10,
                price=100,
                team_count=2,
                initData="" # Not used in service
            )
            # Create dummy admin user if needed
            admin_id = 999999
            await session.merge(User(user_id=admin_id, full_name="Test Admin", username="admin", player_position=Position.CM))
            
            game = await lifecycle_service.create_game(game_data, admin_id)
            logger.info(f"Game Created: ID={game.id}, Status={game.status}")
            
            if game.status != GameStatus.OPEN:
                logger.error("Step 1 Failed: Game Status not OPEN")
                return

            # --- STEP 2: Join Players ---
            logger.info("\n--- STEP 2: Join Players ---")
            players = []
            for i in range(4):
                uid = 1000 + i
                u = User(user_id=uid, full_name=f"Player {i}", username=f"user{i}", player_position=Position.CM, rating=1000)
                await session.merge(u)
                res = await roster_service.join_player(game.id, u)
                if not res.success:
                    logger.error(f"Failed to join player {i}: {res.message}")
                players.append(uid)
            logger.info(f"Joined {len(players)} players.")

            # --- STEP 3: Update Teams ---
            logger.info("\n--- STEP 3: Update Teams ---")
            team_a = players[:2]
            team_b = players[2:]
            
            await roster_service.update_teams(game.id, team_a, team_b, [], {})
            logger.info("Teams Updated.")
            
            # Verify Assignments
            from app.db.models import Signup
            q = await session.execute(select(Signup).where(Signup.game_id == game.id))
            signups = q.scalars().all()
            for s in signups:
                team_str = "A" if s.team == Team.A else "B" if s.team == Team.B else "None"
                logger.info(f"User {s.user_id} -> Team {team_str} ({s.status})")

            # --- STEP 4: Finish Game ---
            logger.info("\n--- STEP 4: Finish Game ---")
            # Create GameStats
            p_stats = [
                PlayerStat(user_id=team_a[0], goals=2), # MVP Candidate
                PlayerStat(user_id=team_b[0], goals=1)
            ]
            
            finish_data = GameFinishRequest(
                game_id=game.id,
                score_a=2,
                score_b=1,
                winner_team=Team.A,
                mvp_user_id=team_a[0],
                mvp_team_a=team_a[0],
                mvp_team_b=team_b[0],
                player_stats=p_stats,
                initData=""
            )
            
            game = await lifecycle_service.finish_game(finish_data)
            logger.info(f"Game Finished: Status={game.status}, Score={game.score_a}:{game.score_b}")
            
            if game.status != GameStatus.FINISHED:
                logger.error("Step 4 Failed: Game not FINISHED")
                
            # Verify Stats/Ratings
            from app.db.models import RatingHistory
            q = await session.execute(select(RatingHistory).where(RatingHistory.game_id == game.id))
            history = q.scalars().all()
            logger.info(f"Rating History entries: {len(history)}")
            for h in history:
                logger.info(f"User {h.user_id}: Rating {h.old_rating} -> {h.new_rating} ({h.change})")
            
            logger.info("\nVerification Successful! Rolling back changes...")
            raise RuntimeError("RollbackIntentional")

if __name__ == "__main__":
    try:
        asyncio.run(run_verification())
    except RuntimeError as e:
        if str(e) == "RollbackIntentional":
            logger.info("Rollback successful. DB pristine.")
        else:
            raise e
    except Exception as e:
        logger.error(f"Verification Failed: {e}", exc_info=True)
