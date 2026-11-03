from datetime import datetime
import logging
from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.domain.dto import CreateGameDTO, FinishGameDTO, UpdateGameDTO
from app.core.domain.tenant_policy import BillingMode, resolve_billing_mode
from app.core.services.stats import StatsService
from app.db.models import Chat, Game, GameStats, GameStatus, Signup, SignupStatus
from app.infrastructure.scheduler.service import SchedulerService

if TYPE_CHECKING:
    from app.core.uow import UnitOfWork

logger = logging.getLogger(__name__)


class GameLifecycleService:
    def __init__(
        self, uow: "UnitOfWork", scheduler: SchedulerService, stats: StatsService
    ):
        self.uow = uow
        self.scheduler = scheduler
        self.stats = stats

    @property
    def session(self) -> AsyncSession:
        return self.uow.session

    async def create_game(self, data: CreateGameDTO, creator_id: int) -> Game:
        """
        Creates a new game, enforces tenant billing mode, handles auto-joins, and schedules lifecycle tasks.
        """
        chat = await self.session.get(Chat, data.chat_id)
        if not chat:
            chat = Chat(chat_id=data.chat_id, title="Unknown Chat (Auto-created)")
            self.session.add(chat)
            await self.session.flush()

        resolved_location = (data.location or "").strip() or (
            chat.default_location or ""
        ).strip()
        if not resolved_location:
            raise ValueError(
                "Match location is required. Please set a location or configure group default."
            )

        billing_mode = resolve_billing_mode(getattr(chat, "billing_mode", None))
        if billing_mode == BillingMode.FREE_CORPORATE:
            resolved_price = 0
            resolved_payment = None
        else:
            resolved_payment = (data.payment_info or "").strip() or (
                chat.payment_info or None
            )
            resolved_price = (
                data.price
                if (data.price is not None and data.price >= 0)
                else (chat.default_price if chat.default_price is not None else 100)
            )

        game = Game(
            chat_id=data.chat_id,
            channel_id=chat.channel_id,
            created_by=creator_id,
            date_time=data.date_time,
            location=resolved_location,
            max_players=data.max_players,
            price=resolved_price,
            payment_info=resolved_payment,
            team_count=data.team_count,
            gk_hours=data.gk_hours,
            registration_hours=data.registration_hours,
            duration=data.duration,
            status=GameStatus.OPEN,
            game_type=data.game_type,
            main_players_count=data.main_players_count,
            signup_limit=data.signup_limit,
        )
        self.session.add(game)
        await self.session.flush()

        if data.auto_join_ids:
            q = select(Signup.user_id).where(
                Signup.game_id == game.id,
                Signup.user_id.in_(data.auto_join_ids),
            )
            res = await self.session.execute(q)
            existing_user_ids = set(res.scalars().all())

            for admin_id in data.auto_join_ids:
                if admin_id not in existing_user_ids:
                    signup = Signup(
                        game_id=game.id,
                        user_id=admin_id,
                        status=SignupStatus.ACTIVE,
                    )
                    self.session.add(signup)
                    existing_user_ids.add(admin_id)

        tz = game.date_time.tzinfo
        now_tz = datetime.now(tz) if tz else datetime.now()
        is_past = game.date_time < now_tz

        if not is_past:
            if data.publish_at:
                pub_at = data.publish_at
                if pub_at.tzinfo is None and tz:
                    pub_at = pub_at.replace(tzinfo=tz)

                if pub_at > now_tz:
                    self.scheduler.schedule_publish(game.id, pub_at)

            self.scheduler.schedule_game_lifecycle(game)

        return game

    async def update_game(self, data: UpdateGameDTO) -> tuple[Game, list[str]]:
        """
        Updates game and reschedules tasks. Returns (Game, changes_list).
        """
        game = await self.session.get(Game, data.game_id)
        if not game:
            raise ValueError("Game not found")

        changes = []

        if data.location and data.location != game.location:
            changes.append(f"📍 Location: {game.location} -> {data.location}")
            game.location = data.location

        if data.date_time:
            if game.date_time != data.date_time:
                from app.core.timezone import format_prague_dt

                old_str = format_prague_dt(game.date_time, "%d.%m %H:%M")
                new_str = format_prague_dt(data.date_time, "%d.%m %H:%M")
                if old_str != new_str:
                    changes.append(f"📅 Date: {old_str} -> {new_str}")

                game.date_time = data.date_time

                if game.id > settings.last_legacy_game_id:
                    self.scheduler.cancel_game_tasks(game.id)
                    self.scheduler.schedule_voting(
                        game.id, game.date_time, duration=game.duration
                    )

        if data.max_players and data.max_players != game.max_players:
            changes.append(f"👥 Slots: {game.max_players} -> {data.max_players}")
            game.max_players = data.max_players

        if data.price is not None and data.price != game.price:
            changes.append(f"💰 Price: {game.price} -> {data.price}")
            game.price = data.price

        if data.payment_info and data.payment_info != game.payment_info:
            game.payment_info = data.payment_info

        if data.gk_hours is not None and data.gk_hours != game.gk_hours:
            game.gk_hours = data.gk_hours

        if data.duration is not None and data.duration != game.duration:
            changes.append(f"🕒 Duration: {game.duration:g}h -> {data.duration:g}h")
            game.duration = data.duration

        if (
            data.registration_hours is not None
            and data.registration_hours != game.registration_hours
        ):
            game.registration_hours = data.registration_hours

        if (
            data.main_players_count is not None
            and data.main_players_count != game.main_players_count
        ):
            game.main_players_count = data.main_players_count

        if data.signup_limit is not None and data.signup_limit != game.signup_limit:
            game.signup_limit = data.signup_limit

        return game, changes

    async def finish_game(self, data: FinishGameDTO) -> Game:
        """
        Finalizes match scores (including 3-team score_c), persists stats, and applies rating deltas.
        Preserves any MVPs already elected via automated ballot if not yet finalized.
        """
        game = await self.session.get(Game, data.game_id)
        if not game:
            raise ValueError("Game not found")

        existing_voted_mvps: set[int] = set()
        if game.status != GameStatus.FINISHED:
            prev_mvp_res = await self.session.execute(
                select(GameStats.user_id).where(
                    GameStats.game_id == game.id,
                    GameStats.is_mvp == True,
                )
            )
            existing_voted_mvps = set(prev_mvp_res.scalars().all())
            if existing_voted_mvps:
                await self.session.execute(
                    delete(GameStats).where(GameStats.game_id == game.id)
                )

        if game.status == GameStatus.FINISHED:
            await self.stats.revert_stats(game.id)
            await self.session.execute(
                delete(GameStats).where(GameStats.game_id == game.id)
            )

        game.score_a = data.score_a
        game.score_b = data.score_b
        game.score_c = getattr(data, "score_c", None)
        game.winner_team = data.winner_team
        game.status = GameStatus.FINISHED

        mvp_ids = set(existing_voted_mvps)
        if getattr(data, "mvp_ids", None):
            mvp_ids.update(data.mvp_ids)
        if data.mvp_team_a:
            mvp_ids.add(data.mvp_team_a)
        if data.mvp_team_b:
            mvp_ids.add(data.mvp_team_b)
        if getattr(data, "mvp_team_c", None):
            mvp_ids.add(data.mvp_team_c)

        processed_users = set()
        stats_to_add = []
        if data.player_stats:
            for p_stat in data.player_stats:
                is_mvp = p_stat.user_id in mvp_ids
                if p_stat.goals > 0 or is_mvp:
                    stat = GameStats(
                        game_id=game.id,
                        user_id=p_stat.user_id,
                        goals=p_stat.goals,
                        is_mvp=is_mvp,
                    )
                    stats_to_add.append(stat)
                    processed_users.add(p_stat.user_id)

        for mid in mvp_ids:
            if mid not in processed_users:
                stats_to_add.append(
                    GameStats(game_id=game.id, user_id=mid, goals=0, is_mvp=True)
                )
                processed_users.add(mid)

        if stats_to_add:
            self.session.add_all(stats_to_add)

        await self.stats.apply_game_results(game, mvp_ids)
        return game
