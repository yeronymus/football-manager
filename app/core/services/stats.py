import logging
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.ratings import (
    ParticipantRatingInput,
    SimplePointsRatingStrategy,
    resolve_rating_strategy,
)
from app.core.domain.tenant_policy import (
    RatingSystem,
    TenantPolicy,
    resolve_tenant_policy,
)
from app.db.models import (
    Chat,
    Game,
    GameStats,
    PlayerProfile,
    RatingHistory,
    Signup,
    SignupStatus,
    Team,
    User,
)

logger = logging.getLogger(__name__)


class StatsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _resolve_policy(self, chat_id: int | None) -> TenantPolicy:
        if chat_id and self.session is not None:
            try:
                chat = await self.session.get(Chat, chat_id)
                if isinstance(chat, Chat):
                    return resolve_tenant_policy(chat)
            except Exception:
                pass
        return resolve_tenant_policy(None)

    async def _fetch_reversion_data(self, game_chat_id: int, user_ids: set[int]):
        """Fetches users and tenant profiles for rating delta reversion."""
        user_map = {}
        profile_map = {}
        if user_ids:
            users_res = await self.session.execute(
                select(User).where(User.user_id.in_(user_ids))
            )
            user_map = {u.user_id: u for u in users_res.scalars().all()}

            profiles_res = await self.session.execute(
                select(PlayerProfile).where(
                    PlayerProfile.user_id.in_(user_ids),
                    PlayerProfile.chat_id == game_chat_id,
                )
            )
            profile_map = {p.user_id: p for p in profiles_res.scalars().all()}
        return user_map, profile_map

    def _revert_history_and_ratings(self, histories, user_map, profile_map):
        """Reverts rating deltas without clobbering ratings earned in subsequent matches."""
        history_ids = []
        for h in histories:
            delta = (
                h.change
                if h.change is not None
                else ((h.new_rating or 100) - (h.old_rating or 100))
            )
            user = user_map.get(h.user_id)
            if user is not None:
                user.rating = (user.rating or 100) - delta
                user.games_played = max(0, (user.games_played or 0) - 1)
                user.stats_matches = max(0, (user.stats_matches or 0) - 1)

            profile = profile_map.get(h.user_id)
            if profile is not None:
                profile.rating = (profile.rating or 100) - delta
                profile.games_played = max(0, (profile.games_played or 0) - 1)
                profile.stats_matches = max(0, (profile.stats_matches or 0) - 1)

            history_ids.append(h.id)
        return history_ids

    def _revert_mvp_stats(self, stats, user_map, profile_map):
        """Reverts MVP counters based on recorded game stats."""
        for s in stats:
            if s.is_mvp:
                user = user_map.get(s.user_id)
                if user:
                    user.stats_mvp = max(0, (user.stats_mvp or 0) - 1)
                profile = profile_map.get(s.user_id)
                if profile:
                    profile.stats_mvp = max(0, (profile.stats_mvp or 0) - 1)

    async def revert_stats(self, game_id: int):
        """Reverts stats and rating deltas for a previously finalized game."""
        game_obj = await self.session.get(Game, game_id)
        if not game_obj:
            return

        history_result = await self.session.execute(
            select(RatingHistory).where(RatingHistory.game_id == game_id)
        )
        histories = history_result.scalars().all()

        stats_result = await self.session.execute(
            select(GameStats).where(GameStats.game_id == game_id)
        )
        stats = stats_result.scalars().all()

        user_ids = {h.user_id for h in histories} | {
            s.user_id for s in stats if s.is_mvp
        }
        user_map, profile_map = await self._fetch_reversion_data(
            game_obj.chat_id, user_ids
        )

        history_ids = self._revert_history_and_ratings(histories, user_map, profile_map)
        self._revert_mvp_stats(stats, user_map, profile_map)

        if history_ids:
            await self.session.execute(
                delete(RatingHistory).where(RatingHistory.id.in_(history_ids))
            )

    @staticmethod
    def _extract_team_scores(game: Game) -> dict[Team, int]:
        scores_map: dict[Team, int] = {}
        if (game.team_count or 2) >= 2:
            scores_map[Team.A] = game.score_a or 0
            scores_map[Team.B] = game.score_b or 0
        if (game.team_count or 2) >= 3:
            scores_map[Team.C] = game.score_c or 0
        return scores_map

    def _calculate_team_points(
        self, game: Game, policy: TenantPolicy | None = None
    ) -> dict[Team, int]:
        """Calculates point change for each team based on ranks, scores, and TenantPolicy."""
        active_policy = policy or TenantPolicy()
        scores_map = self._extract_team_scores(game)
        str_scores = {t.value: sc for t, sc in scores_map.items()}
        str_points = SimplePointsRatingStrategy().compute_team_base_points(
            str_scores, active_policy
        )
        return {Team(k): v for k, v in str_points.items()}

    def _update_single_player_stats(
        self,
        game: Game,
        user: User,
        team: Team,
        profile: PlayerProfile,
        team_points: dict,
        mvp_ids: set[int],
        policy: TenantPolicy | None = None,
        explicit_delta: int | None = None,
    ):
        """Updates tenant PlayerProfile, User stats, and records RatingHistory delta."""
        active_policy = policy or TenantPolicy()
        if not profile:
            profile = PlayerProfile(user_id=user.user_id, chat_id=game.chat_id)
            self.session.add(profile)

        old_rating = profile.rating or 100
        is_mvp = user.user_id in mvp_ids

        if explicit_delta is not None:
            change = explicit_delta
        else:
            change = team_points.get(team, active_policy.rating_loss_points)
            if is_mvp:
                change += active_policy.rating_mvp_bonus

        profile.rating = (profile.rating or 100) + change
        profile.games_played = (profile.games_played or 0) + 1
        profile.stats_matches = (profile.stats_matches or 0) + 1
        if is_mvp:
            profile.stats_mvp = (profile.stats_mvp or 0) + 1

        user.rating = (user.rating or 100) + change
        user.games_played = (user.games_played or 0) + 1
        user.stats_matches = (user.stats_matches or 0) + 1
        if is_mvp:
            user.stats_mvp = (user.stats_mvp or 0) + 1

        self.session.add(
            RatingHistory(
                user_id=user.user_id,
                game_id=game.id,
                old_rating=old_rating,
                new_rating=profile.rating,
                change=change,
            )
        )

    async def apply_game_results(
        self,
        game: Game,
        mvp_ids: set[int] | list[int],
        policy: TenantPolicy | dict | None = None,
    ):
        """Applies rating deltas via configured IRatingStrategy and records RatingHistory."""
        mvp_set = set(mvp_ids or [])
        active_policy = (
            resolve_tenant_policy(policy)
            if policy is not None
            else await self._resolve_policy(game.chat_id)
        )
        team_points = self._calculate_team_points(game, policy=active_policy)

        result = await self.session.execute(
            select(User, Signup.team, PlayerProfile)
            .join(Signup, User.user_id == Signup.user_id)
            .outerjoin(
                PlayerProfile,
                (User.user_id == PlayerProfile.user_id)
                & (PlayerProfile.chat_id == game.chat_id),
            )
            .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
        )
        players_data = result.all()

        explicit_deltas: dict[int, int] = {}
        if active_policy.rating_system == RatingSystem.DYNAMIC_ELO.value:
            strategy = resolve_rating_strategy(active_policy)
            scores_map = {t.value: sc for t, sc in self._extract_team_scores(game).items()}
            inputs = [
                ParticipantRatingInput(
                    user_id=user.user_id,
                    team=team.value if hasattr(team, "value") else str(team or "A"),
                    current_rating=(profile.rating if profile and profile.rating else (user.rating or 100)),
                    games_played=(profile.games_played if profile and profile.games_played is not None else (user.games_played or 0)),
                    is_mvp=(user.user_id in mvp_set),
                )
                for user, team, profile in players_data
                if team is not None
            ]
            explicit_deltas = strategy.compute_player_deltas(inputs, scores_map, active_policy)

        for user, team, profile in players_data:
            self._update_single_player_stats(
                game,
                user,
                team,
                profile,
                team_points,
                mvp_set,
                policy=active_policy,
                explicit_delta=explicit_deltas.get(user.user_id),
            )
