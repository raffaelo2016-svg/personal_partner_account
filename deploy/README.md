# Deploy — операционная справка

## Как работает деплой

`push → main` → GitHub Actions (`.github/workflows/deploy.yml`) подключается по SSH
на прод-сервер и запускает:

1. `git fetch origin main && git reset --hard origin/main` — обновление кода.
2. `bash deploy/deploy.sh` — сборка образов, бэкап БД, миграции, recreate сервисов,
   build фронта, health-check.

Секреты GitHub Actions: `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`. Секретов
приложения там нет.

## Серверный `.env`

Файл `/srv/personal_partner_account/.env` (owner root, `600`) — source of truth
для секретов в проде. В git **не коммитится** и `deploy.sh` его **не трогает**.

### Обязательные переменные в проде

| Переменная | Значение |
|---|---|
| `ENVIRONMENT` | `production` |
| `COOKIE_SECURE` | `true` (без этого backend упадёт на старте) |
| `ALLOWED_HOSTS` | `["kobinetur.uriteh.ru","localhost","127.0.0.1"]` — localhost/127.0.0.1 нужны для docker healthcheck и on-host `curl /health` |
| `SECRET_KEY` | случайные 64+ символа (не `change-me-…`) |
| `DB_PASSWORD` | не `secret` |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | не `minioadmin` |
| `CORS_ORIGINS` | `["https://kobinetur.uriteh.ru"]`, без `"*"` |
| `MINIO_PASSWORD` | совпадает с `S3_SECRET_KEY` |
| `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` | сейчас **тестовый магазин** (`test_…`) — осознанно, до запуска боевых платежей |

Валидация выполняется при старте (`backend/app/config.py`): дефолтные значения
секретов в prod/staging приводят к `RuntimeError`; `COOKIE_SECURE=false` в prod —
тоже `RuntimeError`.

### Как обновить `.env` на проде

```bash
ssh root@<server>
cd /srv/personal_partner_account
cp .env .env.bak-$(date +%Y%m%d-%H%M%S)
nano .env
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps backend celery
# проверить:
docker inspect -f '{{.State.Health.Status}}' personal_partner_account-backend-1
docker logs personal_partner_account-backend-1 --tail 50
```

Добавление новой переменной в код (`backend/app/config.py`) всегда должно
сопровождаться обновлением серверного `.env` **до** автодеплоя, иначе приложение
упадёт на `validate_production_secrets` или словит `RuntimeError` при парсинге
JSON-списков.

## Nginx и TLS

- TLS: Let's Encrypt, автопродление — `certbot --nginx -d kobinetur.uriteh.ru`.
- Серверный конфиг: `/etc/nginx/sites-available/app.conf` — **source of truth**,
  редактируется вручную/через `certbot`, **не синхронизируется автоматически** из
  репо. `deploy.sh` его не трогает.
- Репо-версия `deploy/nginx/app.conf` — целевой (более строгий) конфиг: rate-limits,
  http2, HSTS always, отдельный location для YooKassa webhook, зоны `auth`/`api`/`ws`,
  immutable-кэш для ассетов. На момент написания этой заметки **на прод-сервере
  она не развёрнута** (нет snippets `limits.conf/proxy.conf/ssl.conf` в
  `/etc/nginx/snippets/`). Развернуть — отдельная задача: скопировать snippets,
  заменить `sites-available/app.conf`, `nginx -t && systemctl reload nginx`.

## Firewall

`ufw` разрешает: 22 (SSH), 80/443 (nginx), 10050 (Zabbix agent). Порт 9000 (MinIO)
и 5432 (Postgres) наружу **не** exposed — доступ только внутри docker network.

## Healthcheck и бэкапы

- Docker healthcheck backend: `urlopen http://localhost:8000/health` каждые 15 сек.
  `localhost` должен быть в `ALLOWED_HOSTS`.
- `deploy.sh` делает `curl http://127.0.0.1:8000/health` 20 раз × 2 сек после
  recreate. `127.0.0.1` тоже должен быть в `ALLOWED_HOSTS`.
- Автобэкап БД перед каждой миграцией: `/srv/backups/YYYY-MM-DD_HH-MM-SS.sql.gz`,
  ротация — последние 7 файлов.
- Внешний мониторинг: `deploy/monitoring/` — systemd-таймер для `healthcheck.sh`.

## Что не попадает в docker-образ / git

- `backend/.dockerignore` исключает `.env*`, `.venv`, кэши (`.mypy_cache`,
  `.pytest_cache`, `.ruff_cache`, `.coverage*`), `tests/`, `Dockerfile`, `*.md`.
  Проверка: `docker exec backend ls /app/.env` → no such file.
- `.gitignore` исключает `.env`, `.env.*` (кроме `.env.example`), все кэши,
  `frontend/dist`, `node_modules`, `uploads/`, `storage/`, `*.sqlite3`.
