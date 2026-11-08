from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.routers import billing, dashboard, disciplinary, leaderboards, rosters, tenants, votes
from app.core.domain.dto import CreateGameDTO
from app.core.repositories.announcement_repository import AnnouncementRepository
from app.core.repositories.base import BaseRepository
from app.core.repositories.disciplinary_repository import DisciplinaryRepository
from app.core.repositories.signup_repository import SignupRepository
from app.core.repositories.stats_repository import StatsRepository
from app.core.repositories.tenant_repository import TenantRepository
from app.core.repositories.user_repository import UserRepository
from app.core.repositories.vote_repository import VoteRepository
from app.core.services.game_lifecycle import GameLifecycleService
from app.core.services.game_numbering import clean_location, get_group_game_number
from app.core.services.stats import StatsService
from app.core.uow import UnitOfWork
from app.db.models import (
    AdBanner,
    Chat,
    ChatAdmin,
    Game,
    GameStats,
    GameStatus,
    Position,
    Signup,
    SignupStatus,
    Team,
    User,
    Vote,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_hexagonal_core_layer_purity_and_dashboard_decomposition():
    """
    Enforces Phase 2 architectural invariants:
    1. `app/core/**` has zero imports from `app.bot` or `app.api`.
    2. `app/api/routers/dashboard.py` is decomposed (< 160 lines) and mounts all 6 domain routers.
    3. `UserRepository` inherits from `BaseRepository`.
    """
    assert issubclass(UserRepository, BaseRepository)

    for py_file in (REPO_ROOT / "app" / "core").rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        rel = py_file.relative_to(REPO_ROOT)
        assert "from app.bot" not in content and "import app.bot" not in content, (
            f"Hexagonal layer violation: {rel} imports app.bot"
        )
        assert "from app.api" not in content and "import app.api" not in content, (
            f"Hexagonal layer violation: {rel} imports app.api"
        )

    dash_lines = (
        (REPO_ROOT / "app" / "api" / "routers" / "dashboard.py")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(dash_lines) < 160, f"dashboard.py should stay slim (<160 lines), got {len(dash_lines)}"

    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(dashboard.router)
    route_paths = set(test_app.openapi().get("paths", {}).keys())
    expected_paths = {
        "/dashboard/groups",
        "/dashboard/groups/{chat_id}",
        "/dashboard/groups/{chat_id}/games",
        "/dashboard/groups/{chat_id}/analytics",
        "/dashboard/groups/{chat_id}/players/{target_user_id}",
        "/dashboard/groups/{chat_id}/players/{target_user_id}/card",
        "/dashboard/games/{game_id}",
        "/dashboard/games/{game_id}/guests",
        "/dashboard/games/{game_id}/votes",
        "/dashboard/games/{game_id}/votes/summary",
        "/dashboard/games/{game_id}/notify",
        "/dashboard/games/{game_id}/notify_all_pm",
        "/dashboard/games/{game_id}/notify_group",
        "/dashboard/signups/{signup_id}/toggle_pay",
        "/dashboard/signups/{signup_id}/toggle_late",
    }
    assert expected_paths.issubset(route_paths)

    for mod in (tenants, leaderboards, disciplinary, rosters, votes, billing):
        assert hasattr(mod, "router")


@pytest.mark.asyncio
async def test_unit_of_work_exposes_all_domain_repositories(session):
    chat = Chat(chat_id=-1009601, title="Phase 2 League")
    admin_user = User(user_id=9601, full_name="Admin User", player_position=Position.CM)
    player_user = User(user_id=9602, full_name="Striker User", player_position=Position.ST)
    session.add_all([chat, admin_user, player_user])
    await session.commit()

    session.add(ChatAdmin(chat_id=-1009601, user_id=9601, can_edit_settings=True, can_manage_games=True))
    session.add(
        AdBanner(
            text="Sponsor Banner",
            link="https://example.org",
            is_active=True,
            show_probability=100,
            chat_id=-1009601,
        )
    )
    await session.commit()

    async with UnitOfWork(session=session) as uow:
        assert isinstance(uow.tenant_repo, TenantRepository)
        assert isinstance(uow.signup_repo, SignupRepository)
        assert isinstance(uow.vote_repo, VoteRepository)
        assert isinstance(uow.disciplinary_repo, DisciplinaryRepository)
        assert isinstance(uow.stats_repo, StatsRepository)
        assert isinstance(uow.announcement_repo, AnnouncementRepository)

        # 1. TenantRepository
        assert await uow.tenant_repo.is_chat_admin(-1009601, 9601) is True
        assert await uow.tenant_repo.is_chat_admin(-1009601, 9602) is False
        admin_chats = await uow.tenant_repo.list_for_admin(9601, is_superadmin=False)
        assert [c.chat_id for c in admin_chats] == [-1009601]

        # 2. DisciplinaryRepository
        card = await uow.disciplinary_repo.issue_card(
            user_id=9602,
            chat_id=-1009601,
            card_type="YELLOW",
            weeks=2,
            reason="Late tackle",
            issued_by=9601,
        )
        await uow.commit()
        assert card.card_type == "YELLOW"
        cards_map = await uow.disciplinary_repo.get_active_cards_map(-1009601)
        assert cards_map.get(9602) == "YELLOW"
        revoked = await uow.disciplinary_repo.revoke_active_cards(9602, -1009601)
        await uow.commit()
        assert revoked == 1

        # 3. AnnouncementRepository
        banners = await uow.announcement_repo.list_active(chat_id=-1009601)
        assert len(banners) >= 1 and banners[0].text == "Sponsor Banner"


@pytest.mark.asyncio
async def test_game_sequence_number_o1_lookup_and_repositories(session):
    chat = Chat(chat_id=-1009701, title="Sequence League")
    u1 = User(user_id=9701, full_name="Player A", player_position=Position.GK)
    u2 = User(user_id=9702, full_name="Player B", player_position=Position.ST)
    session.add_all([chat, u1, u2])
    await session.commit()

    mock_scheduler = MagicMock()
    async with UnitOfWork(session=session) as uow:
        lifecycle = GameLifecycleService(uow, mock_scheduler, StatsService(uow.session))
        g1 = await lifecycle.create_game(
            CreateGameDTO(
                chat_id=-1009701,
                date_time=datetime.now() + timedelta(days=1),
                location="Arena One https://maps.example.com/pitch1",
            ),
            creator_id=9701,
        )
        g2 = await lifecycle.create_game(
            CreateGameDTO(
                chat_id=-1009701,
                date_time=datetime.now() + timedelta(days=2),
                location="Arena Two (https://maps.example.com/pitch2)",
            ),
            creator_id=9701,
        )
        await uow.commit()

    # URLs stripped at write time; sequence_number assigned monotonically (1, 2)
    assert g1.location == "Arena One"
    assert g2.location == "Arena Two"
    assert g1.sequence_number == 1
    assert g2.sequence_number == 2

    # O(1) lookup must NOT execute any SQL query when sequence_number is present on Game
    broken_session = AsyncMock()
    broken_session.execute.side_effect = AssertionError("SQL query should not be executed for O(1) sequence_number")
    assert await get_group_game_number(broken_session, g1) == 1
    assert await get_group_game_number(broken_session, g2) == 2

    # Test SignupRepository, VoteRepository & StatsRepository
    s1 = Signup(game_id=g1.id, user_id=9701, status=SignupStatus.ACTIVE, is_paid=False, is_late=True, team=Team.A)
    s2 = Signup(game_id=g1.id, user_id=9702, status=SignupStatus.ACTIVE, is_paid=True, is_late=False, team=Team.B)
    gs2 = GameStats(game_id=g1.id, user_id=9702, goals=3, is_mvp=True)
    v1 = Vote(game_id=g1.id, voter_id=9701, target_id=9702, vote_team=Team.B)
    session.add_all([s1, s2, gs2, v1])
    await session.commit()

    async with UnitOfWork(session=session) as uow:
        unpaid = await uow.signup_repo.list_unpaid_active(g1.id)
        assert len(unpaid) == 1 and unpaid[0][1].user_id == 9701

        roster_rows = await uow.signup_repo.list_by_game_with_users_and_stats(g1.id)
        assert len(roster_rows) == 2

        vote_counts = await uow.vote_repo.get_vote_counts_by_target(g1.id)
        assert vote_counts == {9702: 1}
        summary = await uow.vote_repo.get_votes_summary_by_name(g1.id)
        assert summary == [("Player B", 1)]

        goals = await uow.stats_repo.get_user_group_goals(-1009701, 9702)
        assert goals == 3
        lates = await uow.stats_repo.get_user_group_lates(-1009701, 9701)
        assert lates == 1

    assert clean_location("Pitch 5 https://t.me/test") == "Pitch 5"
