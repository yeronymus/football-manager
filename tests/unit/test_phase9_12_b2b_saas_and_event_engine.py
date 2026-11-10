import datetime
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api.routers.tenants import (
    OrganizationCreateIn,
    QuickSettleIn,
    anonymize_group_member,
    create_b2b_organization,
    get_group_capabilities,
    get_organization_wide_analytics,
    restore_group_member,
    settle_event_without_score,
)
from app.core.domain.sport_presets import get_event_preset, list_event_presets
from app.core.domain.tenant_policy import resolve_effective_modules, resolve_tenant_policy
from app.core.services.billing import calculate_hybrid_settlement, resolve_game_billing
from app.core.services.saas import (
    PlanTier,
    assert_can_create_event,
    check_feature_enabled,
    check_tenant_rate_limit,
    decrypt_secret_envelope,
    encrypt_secret_envelope,
    reset_rate_limit_buckets,
)
from app.db.database import Base
from app.db.models import (
    Chat,
    ChatAdmin,
    ChatMember,
    Game,
    GameStatus,
    Language,
    PlayerProfile,
    Position,
    ShadowIdentityVault,
    Signup,
    SignupStatus,
    User,
)
from app.db.rls import TenantRLSContext, apply_rls_session_vars, generate_rls_policies_sql


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


def test_phase9_universal_event_presets_and_module_overrides():
    all_presets = list_event_presets()
    codes = {p.code for p in all_presets}
    assert {"football", "futsal", "volleyball", "basketball", "padel", "trip", "book_club", "board_games", "generic"}.issubset(codes)

    # Trip preset (e.g. Prague -> Dresden)
    trip = get_event_preset("trip")
    assert trip.category == "trip"
    assert trip.modules.score_tracking_enabled is False
    assert trip.modules.mvp_voting_enabled is False
    assert trip.modules.team_draft_enabled is True  # Carpool grouping
    assert "DRIVER" in trip.roles and "PASSENGER" in trip.roles
    assert trip.localized_terminology("ru")["event_noun"] == "Поездка"
    assert trip.localized_terminology("cs")["event_noun"] == "Výlet"

    # Book Club preset
    club = get_event_preset("book_club")
    assert club.category == "club"
    assert club.modules.roles_enabled is False
    assert club.modules.team_draft_enabled is False
    assert club.modules.score_tracking_enabled is False
    assert club.localized_terminology("ru")["event_noun"] == "Встреча"

    # Per-group module override via TenantPolicy
    dummy_chat = Chat(
        chat_id=-1001,
        title="Prague Book & Quiz Club",
        sport_type="book_club",
        policy={"enabled_modules": {"mvp_voting_enabled": True}},
    )
    resolved = resolve_effective_modules(dummy_chat)
    assert resolved["score_tracking_enabled"] is False
    assert resolved["mvp_voting_enabled"] is True


def test_phase10_hybrid_copay_and_multisport_billing():
    # Total pitch/trip cost = 2000 CZK, 10 participants
    # Company subsidizes 50% (1000 CZK -> left 1000 CZK)
    # 4 participants have MultiSport card (4 * 150 = 600 CZK deducted -> left 400 CZK)
    # Remaining 6 paying participants split 400 CZK -> 67 CZK each
    breakdown = calculate_hybrid_settlement(
        total_cost=2000,
        participant_count=10,
        multisport_count=4,
        employer_subsidy_pct=50,
        multisport_discount=150,
    )
    assert breakdown.employer_share == 1000
    assert breakdown.multisport_total_discount == 600
    assert breakdown.net_participant_pool == 400
    assert breakdown.per_paying_participant_amount == 67
    assert breakdown.per_multisport_participant_amount == 0

    # Verify resolve_game_billing applies employer_subsidy_pct to SPAYD QR
    chat = Chat(
        chat_id=-1002,
        title="Skoda Auto Futsal",
        billing_mode="co_pay_multisport",
        currency="CZK",
        payment_info="19-2000145399/0800",
        policy={"employer_subsidy_pct": 40},
    )
    game = Game(id=77, chat_id=-1002, location="Prague Arena", price=200)
    summary = resolve_game_billing(game, chat=chat, game_number=5)
    assert summary.amount == 120  # 200 * (1 - 0.40)
    assert summary.spayd_payload is not None
    assert "AM:120.00" in summary.spayd_payload


def test_phase11_saas_encryption_rate_limiter_and_rls_sql():
    # BYOB Envelope Encryption
    raw_token = "123456789:AAH_test_enterprise_custom_bot_token_xyz"
    encrypted = encrypt_secret_envelope(raw_token)
    assert encrypted != raw_token
    assert decrypt_secret_envelope(encrypted) == raw_token

    # Feature Gates
    assert check_feature_enabled(PlanTier.FREE, "b2b_export") is False
    assert check_feature_enabled(PlanTier.PRO, "spayd_qr") is True
    assert check_feature_enabled(PlanTier.ENTERPRISE, "b2b_export") is True
    assert check_feature_enabled(PlanTier.ENTERPRISE, "byob_whitelabel") is True

    # Token Bucket Rate Limiter (Noisy Neighbor Protection)
    reset_rate_limit_buckets()
    assert check_tenant_rate_limit("org:1", limit_rps=2, now_ts=100.0) is True
    assert check_tenant_rate_limit("org:1", limit_rps=2, now_ts=100.0) is True
    assert check_tenant_rate_limit("org:1", limit_rps=2, now_ts=100.0) is False
    # Other tenant is unaffected!
    assert check_tenant_rate_limit("org:2", limit_rps=2, now_ts=100.0) is True
    # After 1 second, tokens replenish
    assert check_tenant_rate_limit("org:1", limit_rps=2, now_ts=101.0) is True

    # PostgreSQL RLS DDL generation
    ddl = generate_rls_policies_sql()
    assert any("ALTER TABLE games ENABLE ROW LEVEL SECURITY" in stmt for stmt in ddl)
    assert any("current_setting('app.current_tenant_id'" in stmt for stmt in ddl)


@pytest.mark.asyncio
async def test_phase9_to_12_end_to_end_org_settlement_and_shadow_vault(db_session: AsyncSession):
    admin = User(
        user_id=5001,
        full_name="Yernur Admin",
        username="yeronym",
        player_position=Position.CM,
        is_superadmin=True,
    )
    traveler1 = User(
        user_id=6001,
        full_name="Melih Traveler",
        username="melih",
        player_position=Position.FWD,
        has_multisport_card=True,
    )
    traveler2 = User(
        user_id=6002,
        full_name="Filip Traveler",
        username="filip",
        player_position=Position.DEF,
        has_multisport_card=False,
    )
    db_session.add_all([admin, traveler1, traveler2])

    chat_football = Chat(
        chat_id=-1009001,
        title="Acme Football Prague",
        language=Language.ru,
        sport_type="football",
        billing_mode="spayd_qr",
        payment_info="19-2000145399/0800",
    )
    chat_trip = Chat(
        chat_id=-1009002,
        title="Acme Trip: Prague -> Dresden",
        language=Language.ru,
        sport_type="trip",
        billing_mode="co_pay_multisport",
        payment_info="19-2000145399/0800",
        policy={
            "employer_subsidy_pct": 50,
            "multisport_enabled": True,
            "multisport_discount_amount": 100,
        },
    )
    db_session.add_all([chat_football, chat_trip])
    db_session.add_all(
        [
            ChatAdmin(chat_id=-1009001, user_id=5001),
            ChatAdmin(chat_id=-1009002, user_id=5001),
            ChatMember(chat_id=-1009002, user_id=6001, full_name="Melih Traveler", username="melih", is_registered=True),
            PlayerProfile(chat_id=-1009002, user_id=6001, rating=100, games_played=0, stats_matches=0),
            PlayerProfile(chat_id=-1009002, user_id=6002, rating=100, games_played=0, stats_matches=0),
        ]
    )
    await db_session.commit()

    # 1. Create B2B Organization spanning both Football and Trip chats
    org_res = await create_b2b_organization(
        data=OrganizationCreateIn(
            slug="acme-corp",
            name="Acme Corp Europe",
            plan_tier="enterprise",
            allowed_email_domains=["acme.com"],
            custom_bot_token="999888777:AAH_custom_bot_token",
            chat_ids=[-1009001, -1009002],
        ),
        user_id=5001,
        session=db_session,
    )
    assert org_res["slug"] == "acme-corp"
    assert len(org_res["attached_chats"]) == 2
    org_id = org_res["id"]

    # 2. Check Group Capabilities for the Dresden Trip chat
    caps = await get_group_capabilities(chat_id=-1009002, user_id=5001, session=db_session)
    assert caps["preset_code"] == "trip"
    assert caps["category"] == "trip"
    assert caps["terminology"]["event_noun"] == "Поездка"
    assert caps["modules"]["score_tracking_enabled"] is False
    assert caps["organization"]["slug"] == "acme-corp"

    # 3. Create a Dresden Trip event and settle it WITHOUT football scores
    now = datetime.datetime.now(datetime.timezone.utc)
    trip_event = Game(
        chat_id=-1009002,
        created_by=5001,
        date_time=now + datetime.timedelta(days=2),
        location="Praha hl.n. -> Dresden",
        max_players=10,
        main_players_count=10,
        price=400,
        status=GameStatus.OPEN,
    )
    db_session.add(trip_event)
    await db_session.flush()

    db_session.add_all(
        [
            Signup(game_id=trip_event.id, user_id=6001, status=SignupStatus.ACTIVE),
            Signup(game_id=trip_event.id, user_id=6002, status=SignupStatus.ACTIVE),
        ]
    )
    await db_session.commit()

    settle_res = await settle_event_without_score(
        chat_id=-1009002,
        game_id=trip_event.id,
        data=QuickSettleIn(summary_note="Great trip to Saxon Switzerland!"),
        user_id=5001,
        session=db_session,
    )
    assert settle_res["status"] == "settled"
    assert settle_res["participants_count"] == 2
    # Total cost = 2 * 400 = 800; 50% employer subsidy = 400; 1 MultiSport (-100) => net pool 300 for 1 non-MS traveler
    assert settle_res["hybrid_settlement"]["employer_share"] == 400
    assert settle_res["hybrid_settlement"]["net_participant_pool"] == 300
    assert settle_res["hybrid_settlement"]["per_paying_participant_amount"] == 300

    # Verify attendance counters were incremented without needing match scores
    await db_session.refresh(traveler1)
    assert traveler1.games_played == 1

    # 4. Organization-wide analytics across both Football and Trip branches
    org_analytics = await get_organization_wide_analytics(
        org_id=org_id, user_id=5001, session=db_session
    )
    assert org_analytics["branches_count"] == 2
    assert org_analytics["total_events"] == 1
    assert org_analytics["unique_active_participants"] == 2

    # 5. Two-tier Shadow Identity Vault (GDPR Anonymization + Cold Vault Restore)
    anon_res = await anonymize_group_member(
        chat_id=-1009002,
        target_user_id=6001,
        user_id=5001,
        session=db_session,
    )
    assert anon_res["status"] == "anonymized"
    await db_session.refresh(traveler1)
    assert traveler1.is_anonymized is True
    assert traveler1.full_name.startswith("Former Participant #")
    assert traveler1.username is None

    # Verify encrypted record exists in ShadowIdentityVault
    vault_row = await db_session.get(ShadowIdentityVault, anon_res["vault_id"])
    assert vault_row is not None
    assert "Melih Traveler" not in vault_row.encrypted_payload  # Ciphertext only!

    # Restore user from ShadowIdentityVault when they return
    restore_res = await restore_group_member(
        chat_id=-1009002,
        target_user_id=6001,
        user_id=5001,
        session=db_session,
    )
    assert restore_res["status"] == "restored"
    await db_session.refresh(traveler1)
    assert traveler1.is_anonymized is False
    assert traveler1.full_name == "Melih Traveler"
    assert traveler1.username == "melih"

    # 6. Verify RLS Context Manager and session variable helper
    with TenantRLSContext(tenant_id=-1009002, is_superadmin=False):
        rls_vars = await apply_rls_session_vars(db_session)
        assert rls_vars["app.current_tenant_id"] == "-1009002"
        assert rls_vars["app.is_superadmin"] == "false"

    quota_info = await assert_can_create_event(db_session, -1009002, enforce_strict=True)
    assert quota_info["allowed"] is True
