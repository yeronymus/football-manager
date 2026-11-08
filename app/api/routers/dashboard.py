"""
Dashboard API Aggregator Router.
Decomposed in Phase 2 into focused domain routers (`tenants`, `leaderboards`,
`disciplinary`, `rosters`, `votes`, `billing`) while preserving 100% route and
import backward-compatibility.
"""

from fastapi import APIRouter

from app.api.auth import check_admin_rights, get_user_from_header
from app.api.routers import billing, disciplinary, leaderboards, rosters, tenants, votes
from app.api.routers.billing import (
    notify_all_unpaid_pm,
    notify_group_unpaid,
    notify_player_payment,
    toggle_payment,
)
from app.api.routers.disciplinary import (
    IssueCardIn,
    issue_player_card,
    revoke_player_card,
)
from app.api.routers.leaderboards import (
    GroupAnalyticsOut,
    PlayerActivityOut,
    PlayerCardOut,
    PlayerHistoryGameOut,
    PlayerProfileDetailOut,
    get_group_analytics,
    get_group_player_detail,
)
from app.api.routers.rosters import (
    GameDetailOut,
    GuestCreate,
    PlayerDetailOut,
    StatusUpdate,
    _format_game_players,
    add_guest,
    get_game_details,
    kick_player,
    toggle_signup_late,
    update_player_status,
)
from app.api.routers.tenants import (
    GameSummaryOut,
    GroupOut,
    GroupUpdate,
    delete_game,
    get_dashboard_groups,
    get_group_games,
    update_group_settings,
)
from app.api.routers.votes import (
    VoteDetailOut,
    _get_game_votes_map,
    get_game_votes,
    get_game_votes_summary,
    trigger_voting_dashboard,
)
from app.core.services.cache import cache_service
from app.core.services.game_numbering import clean_location

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

router.include_router(tenants.router)
router.include_router(leaderboards.router)
router.include_router(disciplinary.router)
router.include_router(rosters.router)
router.include_router(votes.router)
router.include_router(billing.router)

__all__ = [
    "router",
    "check_admin_rights",
    "get_user_from_header",
    "cache_service",
    "clean_location",
    "GroupOut",
    "GroupUpdate",
    "GameSummaryOut",
    "get_dashboard_groups",
    "update_group_settings",
    "get_group_games",
    "delete_game",
    "PlayerActivityOut",
    "GroupAnalyticsOut",
    "PlayerHistoryGameOut",
    "PlayerCardOut",
    "PlayerProfileDetailOut",
    "get_group_analytics",
    "get_group_player_detail",
    "IssueCardIn",
    "issue_player_card",
    "revoke_player_card",
    "PlayerDetailOut",
    "GameDetailOut",
    "GuestCreate",
    "StatusUpdate",
    "_format_game_players",
    "get_game_details",
    "toggle_signup_late",
    "add_guest",
    "kick_player",
    "update_player_status",
    "VoteDetailOut",
    "_get_game_votes_map",
    "get_game_votes_summary",
    "get_game_votes",
    "trigger_voting_dashboard",
    "toggle_payment",
    "notify_player_payment",
    "notify_all_unpaid_pm",
    "notify_group_unpaid",
]
