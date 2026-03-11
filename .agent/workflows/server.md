---
description: Как управлять сервером football-manager
---

// turbo-all

1. Сервер: `yernur@10.50.109.14` (dmc12.sin.cvut.cz)
2. Путь: `~/football-manager`
3. Контейнеры: используем `docker compose` (без дефиса)
4. Просмотр логов: `ssh yernur@10.50.109.14 "cd ~/football-manager && docker compose logs --tail=50 app"`
5. Деплой (ПРАВИЛЬНЫЙ СПОСОБ):
   - Локально: `git add . && git commit -m "описание" && git push`
   - На сервере: `ssh yernur@10.50.109.14 "cd ~/football-manager && git pull && docker compose restart app && echo DONE"`
6. Доступ к БД: `ssh yernur@10.50.109.14 "docker exec football-manager-db-1 psql -U postgres -d football_prod -c 'SQL QUERY'"`
7. Перезапуск: `ssh yernur@10.50.109.14 "cd ~/football-manager && docker compose restart app"`
8. ВАЖНО: НЕ использовать scp/rsync — диск сервера медленный, команды зависают
9. ВАЖНО: CloudFlare tunnel нужен для WebApp → `nohup cloudflared tunnel --url http://localhost:8000 > ~/cloudflared.log 2>&1 &`
