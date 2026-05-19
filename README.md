# Football Manager Bot — Semestrální projekt B6B36NSS

Tento repozitář obsahuje semestrální projekt předmětu **B6B36NSS (Návrh softwarových systémů)** na ČVUT FEL. Projekt vyvíjím **samostatně**.

Jedná se o produkční systém pro kompletní správu amatérské fotbalové komunity v Praze prostřednictvím Telegram Botu (Aiogram 3.x) a doprovodného WebApp rozhraní (FastAPI).

---

## 📂 Architektonická dokumentace (Milestones)

Veškeré podklady pro semestrální práci byly úspěšně vypracovány a jsou uloženy ve vyhrazené složce repozitáře:

1. **[Milestone 1 Zpráva](nss_docs/NSS_milestone1.md)** — Architektonická zpráva obsahující analýzu stávajícího stavu (**AS-IS**), návrh cílové modularizované architektury (**TO-BE**), UML diagramy a specifikaci požadavků.
2. **[Milestone 2 Zpráva](nss_docs/NSS_milestone2.md)** — **Architektonická implementace** obsahující detailní popis 5 implementovaných návrhových vzorů (Strategy, Facade, Repository, Unit of Work, Observer), hybridní kešovací vrstvy (Passive + Active Invalidation), message brokeru na Redis Streams (Kafka-like spotřebitelské skupiny), HTTP Interceptoru s asynchronním logováním do Elasticsearch a detailní zabezpečení.

---

## 🛠️ Aktuálně hotová funkcionalita a změny

- **Datová vrstva:** Podle požadavků cvičícího byla provedena revize datových typů. Sloupec `Chat.language` byl plně refaktorován z obecného řetězce (`String`) na typově bezpečný výčtový typ **`Language` Enum (`RU`, `CZ`, `EN`)** (implementováno v `app/db/models.py`).
- **Příprava na Milestone 2:**
  - Infrastruktura pro transakční **Unit of Work** (`app/core/uow.py`).
  - Rozhraní a implementace repozitářů (`app/core/repositories/`).
  - Asynchronní event dispatcher (`app/core/events.py`).

---

## 🚀 Rychlé spuštění a testování

Projekt využívá moderní balíčkovač **`uv`** pro deterministickou správu závislostí a bezproblémové spuštění na stabilním Python 3.12.

### Spuštění testů
Pro lokální ověření funkčnosti a integrity datových modelů spusťte sadu unit testů:
```bash
PYTHONPATH=. uv run --python 3.12 pytest tests/
```

### Spuštění aplikace v Dockeru
Kompletní aplikační stack (FastAPI + PostgreSQL + Redis) lze spustit pomocí Docker Compose:
```bash
docker compose up -d
```
