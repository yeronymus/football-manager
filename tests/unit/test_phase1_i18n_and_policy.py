from datetime import datetime, timedelta
import json
from pathlib import Path
import re
from unittest.mock import MagicMock

from fastapi import FastAPI
import pytest

from app.api.routers import platform
from app.core.domain.dto import CreateGameDTO, FinishGameDTO
from app.core.domain.sport_presets import get_sport_preset, list_sport_presets
from app.core.domain.tenant_policy import OrganizerContact, resolve_tenant_policy
from app.core.i18n import DEFAULT_LOCALES_DIR, LocaleCatalog, format_currency_unit, normalize_locale_code
from app.core.services.billing import (
    build_spayd_payload,
    czech_account_to_iban,
    resolve_game_billing,
    validate_iban_checksum,
)
from app.core.services.game_lifecycle import GameLifecycleService
from app.core.services.qr_svg import render_qr_svg
from app.core.services.roster import RosterService
from app.core.services.stats import StatsService
from app.core.uow import UnitOfWork
from app.db.database import get_session
from app.db.models import (
    Chat,
    Game,
    GameStatus,
    Position,
    Signup,
    SignupStatus,
    Team,
    User,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


async def _asgi_raw_request(
    asgi_app,
    method: str,
    path: str,
    query_string: str = "",
) -> tuple[int, dict[str, str], bytes]:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": query_string.encode("ascii"),
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    sent_events = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent_events.append(message)

    await asgi_app(scope, receive, send)
    start_evt = next(e for e in sent_events if e["type"] == "http.response.start")
    headers = {
        k.decode("latin-1").lower(): v.decode("latin-1")
        for k, v in start_evt.get("headers", [])
    }
    body = b"".join(
        e.get("body", b"") for e in sent_events if e["type"] == "http.response.body"
    )
    return start_evt["status"], headers, body


# ==============================================================================
# 1. CI Locale Key/Placeholder Parity & OPSEC Sanitization Gate (ADR-01)
# ==============================================================================


def test_locale_catalog_key_and_placeholder_parity_and_opsec():
    locale_files = sorted(DEFAULT_LOCALES_DIR.glob("*.json"))
    codes = [f.stem for f in locale_files]
    assert {"en", "ru", "cs"}.issubset(set(codes))

    parsed = {
        f.stem: json.loads(f.read_text(encoding="utf-8")) for f in locale_files
    }
    en_keys = set(parsed["en"].keys())
    assert len(en_keys) >= 340

    for code, messages in parsed.items():
        assert set(messages.keys()) == en_keys, (
            f"Key mismatch in {code}.json: "
            f"missing={en_keys - set(messages.keys())}, extra={set(messages.keys()) - en_keys}"
        )
        for key, en_val in parsed["en"].items():
            en_ph = set(PLACEHOLDER_RE.findall(en_val))
            loc_ph = set(PLACEHOLDER_RE.findall(messages[key]))
            assert loc_ph == en_ph, (
                f"Placeholder mismatch for key '{key}' in {code}.json: "
                f"expected {en_ph}, got {loc_ph}"
            )

    # OPSEC Gate: Zero personal handles, bank accounts, or homelab references
    forbidden_tokens = (
        "yeronym",
        "mukhvmmed",
        "qaddafi_1",
        "napovorotenapravo",
        "fm_metabot",
        "2924402033",
        "147.32.107.65",
        "57.131.147.83",
    )
    audited_paths = [
        *locale_files,
        REPO_ROOT / "app" / "bot" / "handlers" / "common.py",
        REPO_ROOT / "app" / "web" / "rules.html",
        REPO_ROOT / "app" / "web" / "js" / "i18n.js",
    ]
    for path in audited_paths:
        content_lower = path.read_text(encoding="utf-8").lower()
        for token in forbidden_tokens:
            assert token not in content_lower, f"OPSEC leak '{token}' found in {path.name}"


def test_zero_code_change_locale_autodiscovery_and_normalization(tmp_path: Path):
    assert normalize_locale_code(None) == "en"
    assert normalize_locale_code("cz") == "cs"
    assert normalize_locale_code("cs-CZ") == "cs"
    assert format_currency_unit("CZK", "en") == "CZK"
    assert format_currency_unit("CZK", "ru") == "крон"
    assert format_currency_unit("CZK", "cs") == "Kč"

    (tmp_path / "en.json").write_text(
        json.dumps(
            {
                "_locale_name": "English",
                "_locale_flag": "🇬🇧",
                "hello_player": "Hello, {name}!",
                "only_in_en": "Fallback English text",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "de.json").write_text(
        json.dumps(
            {
                "_locale_name": "Deutsch",
                "_locale_flag": "🇩🇪",
                "hello_player": "Hallo, {name}!",
            }
        ),
        encoding="utf-8",
    )

    custom_catalog = LocaleCatalog(locales_dir=tmp_path, default_locale="en")
    assert "de" in custom_catalog.supported_codes()
    assert custom_catalog.translate("de-DE", "hello_player", name="Lukas") == "Hallo, Lukas!"
    assert custom_catalog.translate("de", "only_in_en") == "Fallback English text"
    assert custom_catalog.translate("fr", "hello_player", name="Jean") == "Hello, Jean!"


# ==============================================================================
# 2. Czech QR Platba (SPAYD 1.0), ČNB Mod-11 IBAN, SVG QR & Billing Modes (ADR-05)
# ==============================================================================


def test_cnb_mod11_iban_spayd_and_offline_qr_svg():
    # Official ČNB IBAN test vector: 19-2000145399/0800 -> CZ6508000000192000145399
    iban = czech_account_to_iban("19-2000145399/0800")
    assert iban == "CZ6508000000192000145399"
    assert validate_iban_checksum(iban) is True

    # Invalid Mod-11 check digit must be rejected
    assert czech_account_to_iban("19-2000145398/0800") is None
    assert czech_account_to_iban("Cash at pitch") is None

    # SPAYD 1.0 payload strips Czech diacritics and formats amount/VS cleanly
    spayd = build_spayd_payload(
        iban_or_account="19-2000145399/0800",
        amount=150,
        currency="CZK",
        variable_symbol=42,
        message="Zápas #7 Pankrác *test*",
    )
    assert spayd == (
        "SPD*1.0*ACC:CZ6508000000192000145399*AM:150.00*CC:CZK"
        "*X-VS:42*MSG:Zapas #7 Pankrac test"
    )

    svg = render_qr_svg(spayd)
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert "<path " in svg and 'd="M' in svg
    assert svg.endswith("</svg>")


@pytest.mark.asyncio
async def test_free_corporate_billing_mode_forces_zero_price(session):
    corp_chat = Chat(
        chat_id=-1009101,
        title="ACME Corp Football",
        billing_mode="free_corporate",
        default_price=200,
        payment_info="19-2000145399/0800",
    )
    creator = User(user_id=9101, full_name="HR Manager", player_position=Position.CM)
    session.add_all([corp_chat, creator])
    await session.commit()

    mock_scheduler = MagicMock()
    async with UnitOfWork(session=session) as uow:
        lifecycle = GameLifecycleService(uow, mock_scheduler, StatsService(uow.session))
        game = await lifecycle.create_game(
            CreateGameDTO(
                chat_id=-1009101,
                date_time=datetime.now() + timedelta(days=2),
                location="Corporate Arena",
                price=250,
                payment_info="19-2000145399/0800",
            ),
            creator_id=9101,
        )
        await uow.commit()

    assert game.price == 0
    assert game.payment_info is None
    summary = resolve_game_billing(game, chat=corp_chat)
    assert summary.is_free is True
    assert summary.amount == 0
    assert summary.spayd_payload is None


# ==============================================================================
# 3. TenantPolicy & SportPresets Parameterization (ADR-02 & ADR-03)
# ==============================================================================


def test_sport_presets_and_organizer_contact_resolution():
    presets = {p.code: p for p in list_sport_presets()}
    assert {"football", "futsal", "volleyball", "basketball", "generic"}.issubset(presets.keys())
    assert get_sport_preset("futsal").default_main_players_count == 10
    assert get_sport_preset("volleyball").has_goalkeeper is False
    assert get_sport_preset("nonexistent").code == "football"

    c_tg = OrganizerContact(role="Admin", name="Org", handle="@org_support")
    assert c_tg.url == "https://t.me/org_support"
    c_mail = OrganizerContact(role="HR", name="Desk", handle="sports@example.org")
    assert c_mail.url == "mailto:sports@example.org"


@pytest.mark.asyncio
async def test_tenant_policy_custom_cancellation_window_and_rating_deltas(session):
    chat = Chat(
        chat_id=-1009201,
        title="Custom Policy Club",
        policy={
            "free_cancellation_hours": 48,
            "rating_win_points": 25,
            "rating_draw_points": 5,
            "rating_loss_points": -12,
            "rating_mvp_bonus": 8,
        },
    )
    u_win = User(user_id=9201, full_name="Winner", player_position=Position.ST, rating=100)
    u_lose = User(user_id=9202, full_name="Loser", player_position=Position.CB, rating=100)
    session.add_all([chat, u_win, u_lose])
    await session.commit()

    policy = resolve_tenant_policy(chat)
    assert policy.free_cancellation_hours == 48
    assert policy.rating_win_points == 25

    # Match in 36 hours: blocked because tenant policy requires 48h notice!
    game = Game(
        chat_id=-1009201,
        created_by=9201,
        date_time=datetime.now() + timedelta(hours=36),
        location="Policy Pitch",
        max_players=10,
        team_count=2,
        status=GameStatus.OPEN,
    )
    session.add(game)
    await session.commit()

    session.add_all(
        [
            Signup(game_id=game.id, user_id=9201, status=SignupStatus.ACTIVE, team=Team.A),
            Signup(game_id=game.id, user_id=9202, status=SignupStatus.ACTIVE, team=Team.B),
        ]
    )
    await session.commit()

    async with UnitOfWork(session=session) as uow:
        roster = RosterService(uow)
        ok, msg, _ = await roster.leave_player(game.id, 9201, is_admin=False, locale="en")
        assert ok is False
        assert "less than" in msg.lower() or "admin" in msg.lower()

    # Finish match -> winner gets +25 +8 (MVP) = +33, loser gets -12
    mock_scheduler = MagicMock()
    async with UnitOfWork(session=session) as uow:
        lifecycle = GameLifecycleService(uow, mock_scheduler, StatsService(uow.session))
        await lifecycle.finish_game(
            FinishGameDTO(
                game_id=game.id,
                score_a=5,
                score_b=2,
                winner_team=Team.A,
                mvp_team_a=9201,
            )
        )
        await uow.commit()

    await session.refresh(u_win)
    await session.refresh(u_lose)
    assert u_win.rating == 133
    assert u_lose.rating == 88


# ==============================================================================
# 4. Shared Platform API Endpoints (/api/v1/*)
# ==============================================================================


@pytest.mark.asyncio
async def test_platform_api_locales_presets_rules_and_spayd_qr(session):
    test_app = FastAPI()
    test_app.include_router(platform.router, prefix="/api/v1")
    test_app.dependency_overrides[get_session] = lambda: session

    chat = Chat(
        chat_id=-1009301,
        title="Prague Tech League",
        language="cs",
        currency="CZK",
        billing_mode="spayd_qr",
        payment_info="19-2000145399/0800",
        policy={
            "free_cancellation_hours": 18,
            "organizer_contacts": [
                {"role": "League Ops", "name": "Coordinator", "handle": "@league_ops_example"}
            ],
        },
    )
    creator = User(user_id=9301, full_name="Organizer", player_position=Position.GK)
    session.add_all([chat, creator])
    await session.commit()

    game = Game(
        chat_id=-1009301,
        created_by=9301,
        date_time=datetime.now() + timedelta(days=3),
        location="Letná Arena",
        price=180,
        payment_info="19-2000145399/0800",
        status=GameStatus.OPEN,
    )
    session.add(game)
    await session.commit()

    # 1) /api/v1/locales
    code_loc, _, raw_loc = await _asgi_raw_request(test_app, "GET", "/api/v1/locales")
    assert code_loc == 200
    body_loc = json.loads(raw_loc)
    assert body_loc["default_locale"] == "en"
    assert {"en", "ru", "cs"}.issubset({item["code"] for item in body_loc["locales"]})

    # 2) /api/v1/locales/cz -> resolves alias to 'cs'
    code_cs, _, raw_cs = await _asgi_raw_request(test_app, "GET", "/api/v1/locales/cz")
    assert code_cs == 200
    body_cs = json.loads(raw_cs)
    assert body_cs["locale"] == "cs"
    assert "Startovné" in body_cs["messages"]["lbl_price"] or len(body_cs["messages"]) >= 340

    # 3) /api/v1/presets/sports
    code_sp, _, raw_sp = await _asgi_raw_request(test_app, "GET", "/api/v1/presets/sports")
    assert code_sp == 200
    body_sp = json.loads(raw_sp)
    assert body_sp["default_sport"] == "football"
    assert len(body_sp["presets"]) >= 5

    # 4) /api/v1/tenants/public-rules (must NEVER leak payment_info)
    code_rules, _, raw_rules = await _asgi_raw_request(
        test_app, "GET", "/api/v1/tenants/public-rules", query_string="chat_id=-1009301"
    )
    assert code_rules == 200
    rules_text = raw_rules.decode("utf-8")
    assert "2000145399" not in rules_text
    body_rules = json.loads(rules_text)
    assert body_rules["language"] == "cs"
    assert body_rules["billing_mode"] == "spayd_qr"
    assert body_rules["policy"]["free_cancellation_hours"] == 18
    assert body_rules["contacts"][0]["url"] == "https://t.me/league_ops_example"

    # 5) /api/v1/billing/games/{id}/spayd & /qr.svg
    code_bill, _, raw_bill = await _asgi_raw_request(
        test_app, "GET", f"/api/v1/billing/games/{game.id}/spayd"
    )
    assert code_bill == 200
    body_bill = json.loads(raw_bill)
    assert body_bill["iban"] == "CZ6508000000192000145399"
    assert body_bill["spayd_payload"].startswith("SPD*1.0*ACC:CZ6508000000192000145399*AM:180.00")

    code_qr, hdrs_qr, raw_qr = await _asgi_raw_request(
        test_app, "GET", f"/api/v1/billing/games/{game.id}/qr.svg"
    )
    assert code_qr == 200
    assert "image/svg+xml" in hdrs_qr.get("content-type", "")
    assert raw_qr.startswith(b"<svg ")
