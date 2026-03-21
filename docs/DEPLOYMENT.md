# 📦 Deployment Guide

Бот работает в Docker на сервере. Деплой — через git push/pull.

## 🖥 Сервер

| Параметр | Значение |
|---|---|
| SSH | `ssh yernur@10.50.109.14` |
| Папка проекта | `~/football-manager` |
| Docker контейнеры | `football-manager-app-1`, `football-manager-db-1`, `football-manager-redis-1` |

> [!IMPORTANT]
> Docker Compose установлен как плагин Docker. Используй `docker compose` (с пробелом), **не** `docker-compose`.

---

## 🚀 Деплой (обновление кода)

**Локально:**
```bash
git add .
git commit -m "описание изменений"
git push
```

**На сервере:**
```bash
ssh yernur@10.50.109.14
cd ~/football-manager && git pull
docker compose restart app
```

---

## 🗃 База данных

**Подключиться к psql:**
```bash
ssh yernur@10.50.109.14
cd ~/football-manager
docker compose exec -u postgres db psql -U postgres -d football
```

**Полезные SQL:**
```sql
-- Последние игры
SELECT id, date_time, status FROM games ORDER BY date_time DESC LIMIT 5;

-- Рейтинг топ-5
SELECT full_name, rating FROM users ORDER BY rating DESC LIMIT 5;
```

---

## 🐞 Troubleshooting

**Проверить логи:**
```bash
ssh yernur@10.50.109.14
cd ~/football-manager && docker compose logs --tail=50 app
```

**Бот упал / перезапускается:**
```bash
docker compose logs --tail=100 app  # найти причину
docker compose restart app
```

**Если меняли модели БД** — создай скрипт `migrate_xyz.py` и запусти:
```bash
docker compose exec app python3 migrate_xyz.py
```

---

## ⚠️ Изменение схемы БД

Поля в `app/db/models.py` **не** применяются автоматически. При добавлении новых колонок нужна ручная миграция, иначе бот упадёт с `UndefinedColumnError`.
