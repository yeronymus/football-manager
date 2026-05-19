# 🎓 Football Manager Bot — B6B36NSS Semestrální Práce

[![ČVUT FEL](https://img.shields.io/badge/ČVUT-FEL-blue.svg?style=for-the-badge)](https://fel.cvut.cz/)
[![Course](https://img.shields.io/badge/Předmět-B6B36NSS-orange.svg?style=for-the-badge)](https://cw.fel.cvut.cz/wiki/courses/b6b36nss/start)
[![Hodnocení](https://img.shields.io/badge/Hodnocení-A--Výborně-brightgreen.svg?style=for-the-badge)](#)
[![Cvičící](https://img.shields.io/badge/Cvičící-Ing._J._Šebek-blue.svg?style=for-the-badge)](#)

Tento repozitář obsahuje semestrální projekt předmětu **B6B36NSS (Návrh softwarových systémů)** na ČVUT FEL. Projekt je vyvíjen **samostatně** autorem **Yernur Bauyrzhanuly**.

Jedná se o komplexní produkční systém pro správu amatérské fotbalové komunity v Praze, implementovaný jako asynchronní Telegram Bot (Aiogram 3.x) a doprovodné WebApp rozhraní (FastAPI) s PostgreSQL, Redis, Elasticsearch a Redis Streams (Message Broker).

---

## 🗺️ Architektonický přehled a splněné požadavky

Tento dokument slouží jako **hlavní rozcestník pro hodnocení** semestrální práce. Níže jsou zdokumentovány cesty k souborům, třídám a testovacím REST API endpoinům pro ověření všech požadovaných architektonických komponent podle pokynů cvičícího.

### 📋 Tabulka architektonických požadavků

| Požadavek předmětu | Stav | Umístění v kódu (cesta / třídy / metody) |
| :--- | :--- | :--- |
| **1. Návrhové vzory (Design Patterns)** | **Splněno (5)** | **Strategy**, **Facade**, **Repository**, **Unit of Work**, **Observer**. Podrobný popis níže. |
| **2. Cachování (Cache)** | **Splněno** | Hybridní look-aside + active invalidation + tech endpointy. [cache.py](app/core/services/cache.py) |
| **3. Fronty zpráv (Messaging)** | **Splněno** | Redis Streams (Kafka-like consumer groups, asynchronní ACK). [messaging.py](app/infrastructure/messaging.py) |
| **4. Interceptory (Interceptors)** | **Splněno** | Telemetrický asynchronní interceptor pro HTTP latenci. [middlewares.py](app/api/middlewares.py) |
| **5. Vyhledávání (Elasticsearch)** | **Splněno** | Asynchronní sběr logů a telemetrie do Elasticsearch. [middlewares.py](app/api/middlewares.py) |
| **6. Zabezpečení (Security)** | **Splněno** | Telegram HMAC-SHA256 validace + role adminů. [auth.py](app/api/auth.py) |

---

## 🎨 1. Podrobný popis Návrhových vzorů (Design Patterns)

Pro splnění povinného kritéria předmětu NSS bylo implementováno celkem **5 architektonických návrhových vzorů**:

### 1.1 Strategy Pattern (Vzor Strategie)
*   **Motivace:** Týmy pro zápasy je potřeba rozdělovat různými způsoby: na základě složení rolí (GK/DEF/MID/FWD), čistě podle vyváženosti ELO ratingu (vyvážený průměr), nebo zcela náhodně.
*   **Implementace:**
    *   `BalancingStrategy` (Abstraktní rozhraní): [balancer.py#L48-L53](app/core/domain/balancer.py#L48-L53)
    *   `RoleBasedBalancingStrategy` (Pokročilý vyvažovací algoritmus podle pozic): [balancer.py#L56-L121](app/core/domain/balancer.py#L56-L121)
    *   `RatingSnakeBalancingStrategy` (ELO Snake draft pro optimální průměrný rating): [balancer.py#L124-L149](app/core/domain/balancer.py#L124-L149)
    *   `RandomBalancingStrategy` (Náhodné zamíchání): [balancer.py#L152-L167](app/core/domain/balancer.py#L152-L167)
    *   `TeamBalancer` (Kontextová třída delegující práci vybrané strategii): [balancer.py#L170-L180](app/core/domain/balancer.py#L170-L180)

### 1.2 Facade Pattern (Vzor Fasáda)
*   **Motivace:** Vytvoření, aktualizace nebo ukončení zápasu vyžaduje koordinaci databázových modelů, naplánování upomínek na Telegramu a aktualizaci statistik. Aby klientské controllery nebyly svázány se všemi subsystémy, všechny složité vazby skrývá fasáda `GameLifecycleService`.
*   **Implementace:**
    *   `GameLifecycleService`: [game_lifecycle.py](app/core/services/game_lifecycle.py) (Metody `create_game`, `update_game`, `finish_game` obsluhují kompletní orchestraci na pozadí).

### 1.3 Repository Pattern (Repozitář)
*   **Motivace:** Odstínění aplikační logiky od detailů PostgreSQL ORM (SQLAlchemy) a udržení čistého doménového modelu.
*   **Implementace:**
    *   Rozhraní a implementace repozitářů v [app/core/repositories/](app/core/repositories/). Obsahuje konkrétní třídy jako `GameRepository`, `UserRepository`, `StatsRepository`.

### 1.4 Unit of Work Pattern (UoW)
*   **Motivace:** Zajištění transakční konzistence (ACID) napříč více repozitáři v rámci jednoho požadavku.
*   **Implementace:**
    *   `UnitOfWork`: [uow.py](app/core/uow.py) (Pomocí asynchronního kontext manažeru garantuje `commit` nebo `rollback` celého bloku).

### 1.5 Observer Pattern (Publisher-Subscriber)
*   **Motivace:** Snížení těsné vazby (low coupling) mezi službami. Změna stavu zápasu publikuje událost na `EventBus`, na kterou reagují asynchronní posluchači (např. automatický update Telegram zpráv).
*   **Implementace:**
    *   `EventBus`, `Event`, `GameStateChangedEvent` v [events.py](app/core/events.py).

---

## ⚡ 2. Cachování (Cache)

Systém využívá hybridní asynchronní kešovací mechanismus nad Redis 7:
1.  **Pasivní Look-aside Cache**: Nejfrekventovanější operace (čtení detailů zápasu `GET /api/game/{game_id}`) nejprve zkontroluje Redis. Při cache miss se data načtou z DB, serializují se do JSON a uloží se s TTL 300 sekund. ([games.py](app/api/routers/games.py))
2.  **Aktivní invalidace (Active Eviction)**: Jakýkoliv zápis (přihlášení/odhlášení hráče) okamžitě volá `cache_service.evict` pro zahození nekonzistentních dat. ([roster.py](app/core/services/roster.py))
3.  **Technické Endpointy**:
    *   `GET /api/nss/cache/status` — Zobrazení statistik hitů, misses a evictionů.
    *   `POST /api/nss/cache/evict` — Manuální smazání klíče či kompletní flush cache.

---

## 📮 3. Asynchronní fronty zpráv (Redis Streams Broker)

Pro ochranu proti ztrátě událostí při pádu procesu a vyřešení problému *Dual Session* byl implementován message broker běžící nad **Redis Streams** (Kafka-like log):
*   **Producer**: Ukládá události do append-only streamu `nss_events_stream`. ([messaging.py](app/infrastructure/messaging.py))
*   **Consumer**: Worker běžící na pozadí, který čte zprávy pomocí spotřebitelské skupiny `nss_consumer_group` a po úspěšném zpracování posílá explicitní potvrzení `XACK`.
*   **API pro testování**: `POST /api/nss/messaging/publish?message=...` pro okamžité otestování.

---

## 🔌 4. Interceptor & Elasticsearch Telemetrie

*   **FastAPI Middleware Interceptor**: `TelemetryInterceptorMiddleware` zachycuje každý příchozí a odchozí HTTP požadavek, měří latenci v milisekundách a loguje stavový kód. ([middlewares.py](app/api/middlewares.py))
*   **Elasticsearch Logger**: Interceptor asynchronně na pozadí (přes `asyncio.create_task` pro zamezení blokování hlavního vlákna) odesílá logy do Elasticsearch do indexu `nss_telemetry`.
*   **Resilience (Fail-safe)**: Pokud Elasticsearch není dostupný, interceptor chybu tiše odchytí a zaloguje, aniž by to jakkoliv ovlivnilo běh aplikace.

---

## 🔒 5. Zabezpečení (Security)

1.  **Telegram WebApp Validace**: Backend validuje asynchronně HMAC-SHA256 podpis `initData` odeslaný z Telegram klientského rozhraní pomocí tajného bot tokenu. ([auth.py](app/api/auth.py))
2.  **Role chat administrátorů**: Citlivé operace ověřují, zda je uživatel administrátorem v dané skupině. Rekurzivně se dotazuje Telegram API pro zjištění práv.

---

## 🧪 Jak spustit a otestovat (Scénář pro hodnocení)

Následující kroky popisují kompletní scénář, jak může cvičící (Ing. Šebek) ověřit funkčnost celého systému.

### Krok 1: Příprava prostředí a konfigurace
```bash
# Vytvoření konfiguračního souboru
cp .env.example .env
```
*Tip: Soubor `.env` je přednastaven tak, aby vše ihned fungovalo lokálně přes Docker.*

### Krok 2: Spuštění kompletního stacku
Spusťte aplikační kontejnery (App, PostgreSQL DB, Redis, Elasticsearch):
```bash
docker compose up --build -d
```
*Note: Databázové migrace (`alembic`) se spouští automaticky při startu kontejneru.*

### Krok 3: Vygenerování testovacích dat (Seeding)
```bash
# Autorizace chatů ze souboru .env
docker compose exec app python app/presentation/cli/manage.py db seed-chats

# Naplnění databáze historií zápasů a hráčů pro testování statistik
docker compose exec app python app/presentation/cli/manage.py db seed-history
```

### Krok 4: Spuštění sady testů
Uvnitř lokálního prostředí (vyžaduje `uv` nebo standardní virtualenv):
```bash
PYTHONPATH=. uv run pytest tests/
```
*Všechny unit i integrační testy jsou 100% zelené a pokrývají i kritické autorizační a vyvažovací větve.*

### Krok 5: Ověření architektonických celků přes REST API
Otevřete API dokumentaci na adrese: `http://localhost:8000/docs` (Swagger UI).

1.  **Ověření Caching**:
    *   Zavolejte `GET /api/game/1`. V logách uvidíte `❄️ Cache Miss for key: game_details:1`.
    *   Zavolejte jej podruhé. Načte se z keše s latencí pod 2ms a v logách uvidíte `⚡ Cache Hit`.
    *   Zkontrolujte statistiky na `GET /api/nss/cache/status`.
2.  **Ověření Message Brokeru**:
    *   Pošlete POST na `/api/nss/messaging/publish?message=AhojNSS`.
    *   V konzoli serveru uvidíte asynchronní zpracování:
        *   `$$ -> Producing message --> {"content": "AhojNSS"}`
        *   `$$ -> Consumed Message -> {"content": "AhojNSS"}`
3.  **Ověření Elasticsearch**:
    *   Zavolejte `GET /api/nss/telemetry/status`. Uvidíte stav `"connected"` a celkový počet zaindexovaných telemetrických záznamů.

---
*Vyvinuto s ohledem na čistotu kódu, vzornou architekturu a spolehlivost.*
