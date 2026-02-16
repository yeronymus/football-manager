---
description: Как управлять сервером football-manager
---

// turbo-all

1. Сервер: `ubuntu@yernur-vm1.sin.cvut.cz`
2. Путь: `~/football-prod`
3. Контейнеры: используем `docker-compose`
4. Просмотр логов: `ssh ubuntu@yernur-vm1.sin.cvut.cz "cd ~/football-prod && docker-compose logs --tail=100 app"`
5. Деплой: использовать локальный `./prod.sh`
6. Доступ к БД: `ssh ubuntu@yernur-vm1.sin.cvut.cz "cd ~/football-prod && docker-compose exec -u postgres db psql -U postgres -d football"`
