# Multi-Tenant Configuration, Billing Modes & Internationalization (`i18n`)

This document describes the parameterization and localization architecture of the **Sports Logistics & Team Engagement Platform** (`ADR-01`, `ADR-02`, `ADR-03`, and `ADR-05`).

---

## 1. Single-Source JSON Internationalization (`ADR-01`)

### Architecture Principles
1. **Universal English Default (`en`)**: Every subsystem — Telegram Bot, FastAPI routers, background scheduler tasks, and Telegram Mini Apps — defaults strictly to English (`en`) whenever user or group locale preferences are unset or unrecognized.
2. **Single-Source Locale Catalog**: All translations live in [`app/locales/`](../app/locales/) as flat UTF-8 JSON dictionaries:
   - [`app/locales/en.json`](../app/locales/en.json) — Canonical reference dictionary (`🇬🇧 English`)
   - [`app/locales/ru.json`](../app/locales/ru.json) — Russian (`🇷🇺 Русский`)
   - [`app/locales/cs.json`](../app/locales/cs.json) — Czech (`🇨🇿 Čeština`, automatically normalizing legacy `cz`, `ces`, and `cs-CZ` aliases to ISO 639-1 `cs`)
3. **Zero-Code-Change Locale Auto-Discovery**: Dropping any new `<code >.json` file (e.g., `de.json` or `es.json`) into `app/locales/` with `_locale_name` and `_locale_flag` metadata automatically registers the language in:
   - `LocaleCatalog` (`app/core/i18n.py`)
   - Bot `/language` inline keyboard (`app/bot/handlers/language_handlers.py`)
   - Public WebApp catalog endpoints (`GET /api/v1/locales` and `GET /api/v1/locales/{lang}`)
   - Shared WebApp frontend (`app/web/js/i18n.js`)
4. **Blocking CI Parity Gate**: Automated unit tests (`tests/unit/test_phase1_i18n_and_policy.py`) assert 100% key and `{placeholder}` equivalence across every `app/locales/*.json` file on every test run.

### Adding a New Language
1. Copy `app/locales/en.json` to `app/locales/<iso_code>.json` (for example, `app/locales/de.json`).
2. Set `"_locale_name": "Deutsch"` and `"_locale_flag": "🇩🇪"`, and translate message values while keeping `{placeholder}` names intact.
3. Run `pytest tests/unit/test_phase1_i18n_and_policy.py` to verify key and placeholder parity.

---

## 2. Three-Tier Hierarchical Parameterization (`ADR-02`)

Hardcoded group constants, organizer handles, magic timeouts, and static rating deltas are replaced by a three-tier configuration hierarchy:

| Tier | Scope | Source | Key Parameters |
|:---|:---|:---|:---|
| **Tier 1: Platform Config** | Instance-wide defaults | Environment / `.env` (`app/config.py`) | `DEFAULT_LOCALE`, `DEFAULT_TIMEZONE`, `DEFAULT_CURRENCY`, `SUPPORT_CONTACT`, `REGISTRATION_MODE` |
| **Tier 2: Tenant Policy** | Per Telegram group / department | `chats` columns + `chats.policy` (`JSON`) | `language`, `currency`, `timezone`, `sport_type`, `billing_mode`, `free_cancellation_hours`, `mvp_voting_window_hours`, `rating_win_points`, `rating_draw_points`, `rating_loss_points`, `rating_mvp_bonus`, `organizer_contacts` |
| **Tier 3: Match Settings** | Individual match override | `games` table (`CreateGameDTO`) | `location`, `date_time`, `price`, `payment_info`, `max_players`, `main_players_count`, `team_count`, `duration`, `gk_hours`, `registration_hours`, `signup_limit` |

### Dynamic Public Rules (`rules.html`)
The Community Rules & Match Guide Mini App (`app/web/rules.html`) fetches `GET /api/v1/tenants/public-rules?chat_id=<id>` at load time and dynamically renders:
- Cancellation deadline (`free_cancellation_hours`)
- Tenant billing workflow (`manual`, `spayd_qr`, or `free_corporate`)
- Tenant MMR rating table (`rating_win_points`, `rating_draw_points`, `rating_loss_points`, `rating_mvp_bonus`)
- Configured `organizer_contacts` (never exposing private bank account numbers or developer personal details)

---

## 3. Multi-Sport Discipline Presets (`ADR-03`)

Sport disciplines are defined declaratively in [`app/core/presets/sport_presets.json`](../app/core/presets/sport_presets.json) and served via `GET /api/v1/presets/sports`:

| Preset Code | Default Pitch Size | Total Squad | Goalkeeper Priority | Supported Team Counts |
|:---|:---:|:---:|:---:|:---:|
| `football` | `22` (`11v11`) | `26` | Yes | `2, 3, 4` |
| `futsal` | `10` (`5v5`) | `15` | Yes | `2, 3, 4` |
| `volleyball` | `12` (`6v6`) | `18` | No | `2, 3` |
| `basketball` | `10` (`5v5`) | `15` | No | `2, 3` |
| `generic` | `12` (`6v6`) | `16` | No | `2, 3, 4` |

---

## 4. Enterprise Billing Modes & Czech `QR Platba` (`ADR-05`)

Each tenant configures `billing_mode` independently in the Admin Hub:

1. **`manual` (Manual Bank Transfer / Cash)**:
   - Displays configured `price`, localized `currency` (`CZK` / `EUR` / `USD`), and free-text `payment_info`.
   - Enables admin payment tracking (`Paid` / `Unpaid`) and DM / group debtor reminders.
2. **`spayd_qr` (Czech QR Platba — `SPAYD 1.0`)**:
   - Validates domestic Czech bank accounts (`[prefix-]account/bank_code` via Czech National Bank **Modulo-11** weights) or ISO 13616 **IBAN** (**Modulo 97-10**) in `app/core/services/billing.py`.
   - Builds standard **Short Payment Descriptor (`SPD*1.0`)** strings with automatic ASCII sanitization, amount (`AM`), currency (`CC`), and match Variable Symbol (`X-VS`).
   - Renders crisp, self-contained **ISO/IEC 18004 SVG QR codes** completely offline (`app/core/services/qr_svg.py` → `GET /api/v1/billing/games/{game_id}/qr.svg`) with zero external third-party API calls or data leakage.
3. **`free_corporate` (Corporate / HR-Funded Free Mode)**:
   - Automatically enforces `price = 0` and clears bank account requirements when creating matches.
   - Displays a clean *Corporate Free* badge on match announcements and Mini App cards while hiding debtor counters, payment toggles, and payment reminder buttons.
