# Football Manager Bot — NSS Semestrální práce (Milestone 2)

**Předmět:** B6B36NSS — Návrh softwarových systémů  
**Autor:** Yernur Bauyrzhanuly  
**Repozitář:** [gitlab.fel.cvut.cz/bauyryer/football-bot-nss](https://gitlab.fel.cvut.cz/bauyryer/football-bot-nss)  
**Technologie:** Python 3.11 · FastAPI · Aiogram 3.x · PostgreSQL 15 · Redis 7 · Docker · Elasticsearch 7

---

Tento dokument slouží jako **hlavní rozcestník pro hodnocení** druhé odevzdávané části (Milestone 2) semestrální práce z předmětu NSS. Podle pokynů vyučujícího (Ing. J. Šebek) jsou níže jasně zdokumentovány cesty k souborům, třídám a testovacím REST API endpoinům pro ověření všech požadovaných architektonických komponent.

---

## 🗺️ Přehled splněných požadavků a jejich umístění v kódu

| Architektonický požadavek | Stav | Umístění v kódu (cesta / třídy / metody) |
| :--- | :--- | :--- |
| **1. Návrhové vzory (Design Patterns)** | **Splněno** | Celkem 5 vzorů: **Strategy**, **Facade**, **Repository**, **Unit of Work**, **Observer**. Podrobné popisy níže. |
| **2. Cachování (Cache)** | **Splněno** | Passive look-aside caching + active cache invalidation + technical reset endpoint. [cache.py](file:///home/yeronym/Documents/fmBot/football-manager/app/core/services/cache.py) |
| **3. Fronty zpráv (Messaging)** | **Splněno** | Redis Streams (Kafka-like log, Producer/Consumer, consumer groups, async processing). [messaging.py](file:///home/yeronym/Documents/fmBot/football-manager/app/infrastructure/messaging.py) |
| **4. Interceptory (Interceptors)** | **Splněno** | Interceptor pro sběr HTTP telemetrie, měření latence a asynchronní export logů. [middlewares.py](file:///home/yeronym/Documents/fmBot/football-manager/app/api/middlewares.py) |
| **5. Vyhledávání (Elasticsearch)** | **Splněno** | Asynchronní indexace HTTP telemetrie v Elasticsearch s fail-safe fallbackem. [middlewares.py](file:///home/yeronym/Documents/fmBot/football-manager/app/api/middlewares.py) |
| **6. Zabezpečení (Security)** | **Splněno** | HMAC-SHA256 validace Telegram `initData` + ověření rolí administrátora. [auth.py](file:///home/yeronym/Documents/fmBot/football-manager/app/api/auth.py) |

---

## 🎨 1. Návrhové vzory (Design Patterns)

Pro splnění povinného kritéria (minimálně 5 vzorů, které dávají smysl a zapadají do logiky systému) byly implementovány následující vzory:

### 1.1 Strategy Pattern (Vzor Strategie)
*   **Motivace:** Týmy pro přátelská utkání je potřeba rozdělovat různými způsoby: na základě složení rolí (GK/DEF/MID/FWD), čistě podle vyváženosti ELO ratingu, nebo zcela náhodně pro tréninkové účely.
*   **Třídy a cesty:** 
    *   `BalancingStrategy` (Abstraktní rozhraní): [balancer.py#L48-L53](file:///home/yeronym/Documents/fmBot/football-manager/app/core/domain/balancer.py#L48-L53)
    *   `RoleBasedBalancingStrategy` (Pokročilý vyvažovací algoritmus): [balancer.py#L56-L121](file:///home/yeronym/Documents/fmBot/football-manager/app/core/domain/balancer.py#L56-L121)
    *   `RatingSnakeBalancingStrategy` (ELO Snake draft pro optimální průměrný rating): [balancer.py#L124-L149](file:///home/yeronym/Documents/fmBot/football-manager/app/core/domain/balancer.py#L124-L149)
    *   `RandomBalancingStrategy` (Náhodné zamíchání): [balancer.py#L152-L167](file:///home/yeronym/Documents/fmBot/football-manager/app/core/domain/balancer.py#L152-L167)
    *   `TeamBalancer` (Kontextová třída delegující práci vybrané strategii): [balancer.py#L170-L180](file:///home/yeronym/Documents/fmBot/football-manager/app/core/domain/balancer.py#L170-L180)

### 1.2 Facade Pattern (Vzor Fasáda)
*   **Motivace:** Vytvoření, aktualizace nebo ukončení zápasu vyžaduje koordinaci databázových modelů, naplánování upomínek na Telegramu a aktualizaci statistik. Aby klientské controllery nebyly svázány se všemi subsystémy, všechny složité vazby skrývá fasáda `GameLifecycleService`.
*   **Třídy a cesty:**
    *   `GameLifecycleService`: [game_lifecycle.py](file:///home/yeronym/Documents/fmBot/football-manager/app/core/services/game_lifecycle.py) (Metody `create_game`, `update_game`, `finish_game` obsluhují kompletní orchestraci na pozadí).

### 1.3 Repository Pattern
*   **Motivace:** Odstínění aplikační logiky od detailů PostgreSQL ORM (SQLAlchemy) a udržení čistého doménového modelu.
*   **Třídy a cesty:**
    *   `GameRepository` a `UserRepository` v [repositories](file:///home/yeronym/Documents/fmBot/football-manager/app/core/repositories/).

### 1.4 Unit of Work Pattern
*   **Motivace:** Zajištění transakční konzistence napříč více repozitáři. Všechny databázové operace v rámci jednoho requestu jsou uloženy jako atomická operace (ACID).
*   **Třídy a cesty:**
    *   `UnitOfWork`: [uow.py](file:///home/yeronym/Documents/fmBot/football-manager/app/core/uow.py)

### 1.5 Observer Pattern (Publisher-Subscriber)
*   **Motivace:** Snížení těsné vazby (low coupling) mezi službami. Změna stavu zápasu publikuje událost na `EventBus`, na kterou reagují asynchronní posluchači (např. automatický update Telegram zpráv bez přímé závislosti servisní vrstvy na Telegram API).
*   **Třídy a cesty:**
    *   `EventBus`, `Event`, `GameStateChangedEvent` atd. v [events.py](file:///home/yeronym/Documents/fmBot/football-manager/app/core/events.py).

---

## ⚡ 2. Cachování (Cache)

Implementován hybridní systém (Passive look-aside + Active cache invalidation) s použitím asynchronního klienta Redis 7.

### 2.1 Pasivní cachování (Passive Look-aside Cache)
*   **Koncept:** Čtení detailů zápasu a soupisky (`GET /api/game/{game_id}`) je nejfrekventovanější operace v celém systému (využívají ji všichni přihlášení hráči). Endpoint nejprve zkontroluje přítomnost dat v Redis. Při cache miss se data dotáhnou z DB, serializují se do JSONu a uloží do Redis s TTL 300 sekund.
*   **Kód:** [games.py#L11-L20](file:///home/yeronym/Documents/fmBot/football-manager/app/api/routers/games.py#L11-L20) a [cache.py](file:///home/yeronym/Documents/fmBot/football-manager/app/core/services/cache.py).

### 2.2 Aktivní invalidace cache (Active Cache Invalidation)
*   **Koncept:** Při jakékoliv zápisové operaci nad soupiskou (hráč se zapíše, odepíše, nebo admin změní soupisku) se cache pro daný zápas okamžitě invaliduje (`cache_service.evict`), aby se zabránilo zobrazení nekonzistentních dat.
*   **Kód:** Integrováno do metod `join_player`, `leave_player` a `recalculate_roster` v [roster.py](file:///home/yeronym/Documents/fmBot/football-manager/app/core/services/roster.py).

### 2.3 Technický Endpoint pro manuální invalidizaci
*   Pro snadnou údržbu na produkci a debugging byl vytvořen dedikovaný endpoint, kterým lze přinutit aplikaci vymazat konkrétní klíč nebo kompletně vyčistit celou cache.
*   **Endpointy:** 
    *   `GET /api/nss/cache/status` — Zobrazení metrik (hits, misses, evictions).
    *   `POST /api/nss/cache/evict` — Manuální vymazání klíče či flush celé DB.

---

## 📮 3. Fronty zpráv (Messaging)

Pro vyřešení architektonických problémů **Volatile Event Bus** (ztráta událostí při restartu procesu) a **Dual Session** (transakční nekonzistence s Telegram API) byl in-memory Event Bus nahrazen robustním **Redis Streams** systémem. Redis Streams funguje na principu append-only logu a plně odpovídá chování brokeru **Kafka** (podpora témat/topiků, spotřebitelských skupin/consumer groups, zpráv o doručení/ACK).

### 3.1 Producer (Producent)
*   **Koncept:** Při vyvolání události (např. registrace testovací zprávy) producent asynchronně odešle payload do Redis Streamu `nss_events_stream` pod daným tématem a zapíše podrobný log.
*   **Kód:** `MessageProducer` v [messaging.py](file:///home/yeronym/Documents/fmBot/football-manager/app/infrastructure/messaging.py).
*   **Logovací šablona:** `$$ -> Producing message --> <payload>`

### 3.2 Consumer (Konzument)
*   **Koncept:** Samostatný worker běžící na pozadí aplikace, který pomocí spotřebitelské skupiny `nss_consumer_group` a metody `XREADGROUP` asynchronně čte zprávy ze streamu. Garantuje, že každá zpráva bude doručena právě jednou. Jakmile ji úspěšně zpracuje, odešle potvrzení (`XACK`). Pokud worker spadne, po restartu zpracuje zprávy, které nebyly potvrzeny.
*   **Kód:** `MessageConsumer` v [messaging.py](file:///home/yeronym/Documents/fmBot/football-manager/app/infrastructure/messaging.py).
*   **Logovací šablona:** `$$ -> Consumed Message -> <payload>`

---

## 🔌 4. Interceptory (HTTP Middleware) a Elasticsearch

### 4.1 Interceptor (Middleware)
*   **Koncept:** Implementován jako asynchronní FastAPI Middleware `TelemetryInterceptorMiddleware`. Zachycuje každý příchozí HTTP request před jeho zpracováním controllerem a následně i po jeho dokončení. Měří latenci v milisekundách a automaticky loguje status code.
*   **Kód:** [middlewares.py](file:///home/yeronym/Documents/fmBot/football-manager/app/api/middlewares.py).

### 4.2 Elasticsearch Integration
*   **Koncept:** Po dokončení requestu Interceptor asynchronně (pomocí `asyncio.create_task` pro nulové zatížení hlavního vlákna) odešle strukturovaný JSON log do Elasticsearch instance běžící na `http://localhost:9200/nss_telemetry/_doc`.
*   **Fail-safe mechanizmus:** Pokud Elasticsearch neběží (např. v testovacím prostředí), middleware chybu tiše odchytí a pokračuje dál bez jakéhokoliv ovlivnění uživatelského zážitku či spolehlivosti aplikace.

---

## 🔒 5. Zabezpečení (Security)

Bezpečnost celého API je postavena na protokolu splňujícím požadavky na zabezpečení v kurzu NSS:
*   **Telegram HMAC-SHA256 validace:** Pro veškeré standardní akce (přihlášení, zápis, zobrazení zápasu) se na backendu ověřuje podpis `initData` odeslaný z Telegram WebApp. Klíčem pro podpis je tajný token Telegram bota, což zaručuje, že data nemohou být podvržena.
*   **Kód:** `validate_init_data` a `get_user_from_header` v [auth.py](file:///home/yeronym/Documents/fmBot/football-manager/app/api/auth.py).
*   **Ochrana administrace:** Citlivé operace (např. ruční změna soupisky) procházejí kontrolou práv `check_admin_rights`, která ověřuje, zda má daný uživatel roli administrátora v příslušném chatu.

---

## 🧪 Jak otestovat (Scénář pro vyučujícího v 5 krocích)

Vyučující může veškeré implementované technologie otestovat přímo přes REST API pomocí Swagger UI, Postmanu nebo curl.

### Krok 1: Spuštění aplikace
Aplikace se spouští standardně pomocí Docker Compose (který nyní obsahuje i Elasticsearch):
```bash
docker-compose up --build -d
```

### Krok 2: Ověření Interceptoru a Caching
1. Otevřete prohlížeč na detailu libovolného zápasu (např. `http://localhost:8000/api/game/1`).
2. V konzoli serveru uvidíte log z **Interceptoru**:
   `🔌 [Interceptor] Incoming Request: GET /api/game/1 from IP: 127.0.0.1`
   `✅ [Interceptor] Response Status: 200 | Duration: 18.52ms`
3. V logu také uvidíte zprávu o prvním minutí cache (**Cache Miss**):
   `❄️ Cache Miss for key: game_details:1`
4. Obnovte stránku (F5). Zápas se nyní načte z **Redis cache**:
   `⚡ Cache Hit for key: game_details:1`
   `✅ [Interceptor] Response Status: 200 | Duration: 1.20ms` (Latence klesla na minimum!)

### Krok 3: Technický API Endpoint pro Cache
1. Pošlete GET request na `/api/nss/cache/status` (lze provést přímo přes prohlížeč). Uvidíte aktuální stav, název poskytovatele a statistiky hitů/missů.
2. Pošlete POST request na `/api/nss/cache/evict?all_keys=true`. Cache se okamžitě kompletně invaliduje.
3. Při dalším načtení detailu zápasu uvidíte opět `Cache Miss`, protože data byla zahozena.

### Krok 4: Testování Message Brokeru (Kafka-like Redis Streams)
1. Pošlete POST request na `/api/nss/messaging/publish?message=HelloNSS`.
2. V logу konzole okamžitě uvidíte, jak **Producer** uložil zprávu do streamu:
   `$$ -> Producing message --> {"content": "HelloNSS"}`
3. Zlomky sekundy na to asynchronní **Consumer** na pozadí zprávu přečetl ze streamu, zpracoval ji a odeslal ACK:
   `$$ -> Consumed Message -> {"content": "HelloNSS"}`

### Krok 5: Vyhledávání a Telemetrie v Elasticsearch
Pošlete GET request na `/api/nss/telemetry/status` pro zobrazení stavu připojení k Elasticsearch. Pokud ES kontejner běží, uvidíte `"status": "connected"`. Všechny logy z kroku 2 a 3 jsou již zaindexovány v indexu `nss_telemetry`!
