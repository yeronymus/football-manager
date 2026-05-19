# Football Manager Bot — Semestrální projekt B6B36NSS

Tento repozitář obsahuje semestrální projekt předmětu **B6B36NSS (Návrh softwarových systémů)** na ČVUT FEL. Projekt vyvíjím **samostatně**.

Jedná se o produkční systém pro kompletní správu amatérské fotbalové komunity v Praze prostřednictvím Telegram Botu (Aiogram 3.x) a doprovodného WebApp rozhraní (FastAPI).

---

## 📂 Architektonická dokumentace (Milestone 1)

Veškeré podklady pro první milník semestrální práce byly úspěšně vypracovány, zrevidovány podle požadavků a jsou uloženy ve vyhrazené složce repozitáře:

1. **[Milestone 1 Zpráva](nss_docs/NSS_milestone1.md)** — Kompletní architektonická zpráva obsahující:
   - Detailní analýzu současného stavu (**AS-IS**), identifikaci anti-patternů (God Object, protékání vrstev, chybějící transakční izolace, volatile event bus).
   - Návrh cílové modularizované architektury (**TO-BE**) typu Modular Monolith s Vertical Slice uspořádáním.
   - Kompletní specifikace a parametry pro **Redis Look-Aside Cache** a **Redis Streams (Outbox Worker)**.
   - Definice funkčních a nefunkčních požadavků.
2. **[UML Diagramy (Mermaid)](nss_docs/NSS_presentation.md)** — Interaktivní komponentní diagramy, sequence diagramy (se znázorněním commit/rollback try-catch hranic) a class diagramy pro stávající i cílový stav.
3. **[Prezentační scénář](nss_docs/NSS_presentation_script.md)** — Doprovodný text pro obhajobu prvního milníku.

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
