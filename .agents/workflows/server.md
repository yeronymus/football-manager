---
description: Как управлять сервером football-manager
---

## Подключение к серверу

```bash
ssh yernur@10.50.109.14
cd ~/football-manager
```

## Деплой (обновление кода)

**Локально** — закоммить и запушить:
```bash
git add .
git commit -m "описание"
git push
```

**На сервере** — подтянуть и перезапустить:
```bash
ssh yernur@10.50.109.14
cd ~/football-manager && git pull
docker compose restart app
```

> ⚠️ Используй `docker compose` (с пробелом), не `docker-compose`

## Просмотр логов

```bash
docker compose logs --tail=50 app
```

## База данных

```bash
docker compose exec -u postgres db psql -U postgres -d football
```

## Миграция БД (после изменения моделей)

```bash
docker compose exec app python3 migrate_xyz.py
```
