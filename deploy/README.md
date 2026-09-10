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
| `ALLOWED_HOSTS` | `["finzdorovie.ru","www.finzdorovie.ru","localhost","127.0.0.1"]` — localhost/127.0.0.1 нужны для docker healthcheck и on-host `curl /health` |
| `SECRET_KEY` | случайные 64+ символа (не `change-me-…`) |
| `DB_PASSWORD` | не `secret` |
| `S3_ENDPOINT` | `http://minio:9000` |
| `S3_PUBLIC_ENDPOINT` | `https://finzdorovie.ru` |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | не `minioadmin` |
| `CORS_ORIGINS` | `["https://finzdorovie.ru","https://www.finzdorovie.ru"]`, без `"*"` |
| `MINIO_PASSWORD` | совпадает с `S3_SECRET_KEY` |
| `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` | сейчас **тестовый магазин** (`test_…`) — осознанно, до запуска боевых платежей |
| `PUBLIC_APP_URL` | `https://finzdorovie.ru` — используется в ссылках восстановления пароля |
| `SMTP_HOST`, `SMTP_PORT` | SMTP-сервер корпоративной почты и его SSL-порт |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | логин и пароль приложения почтового ящика для системных писем |
| `SMTP_FROM_EMAIL` | адрес отправителя писем восстановления пароля |
| `SMTP_USE_SSL`, `SMTP_USE_STARTTLS` | для порта 465 обычно `true` / `false` |

Валидация выполняется при старте (`backend/app/config.py`): дефолтные значения
секретов в prod/staging приводят к `RuntimeError`; `COOKIE_SECURE=false` в prod —
тоже `RuntimeError`.

`docker-compose.prod.yml` сам прокидывает контейнерам внутренние адреса
`DATABASE_URL=postgresql+asyncpg://app:<DB_PASSWORD>@db:5432/partner_cabinet` и
`REDIS_URL=redis://redis:6379/0`, чтобы backend не ходил к БД/Redis через
host-порты.

### Как обновить `.env` на проде

```bash
ssh root@<server>
cd /srv/personal_partner_account
cp .env .env.bak-$(date +%Y%m%d-%H%M%S)
nano .env
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps backend celery celery-beat
# проверить:
docker inspect -f '{{.State.Health.Status}}' personal_partner_account-backend-1
docker logs personal_partner_account-backend-1 --tail 50
```

Добавление новой переменной в код (`backend/app/config.py`) всегда должно
сопровождаться обновлением серверного `.env` **до** автодеплоя, иначе приложение
упадёт на `validate_production_secrets` или словит `RuntimeError` при парсинге
JSON-списков.

## DNS, Nginx и TLS

- DNS у регистратора должен указывать на сервер Selectel `161.104.52.194`:
  `A @ → 161.104.52.194`, `A www → 161.104.52.194`.
- TLS: Let's Encrypt, автопродление — сертификат для `finzdorovie.ru` и
  `www.finzdorovie.ru`.
- Репо-версия `deploy/nginx/app.conf` — source of truth для приложения:
  `deploy.sh` синхронизирует её и snippets в `/etc/nginx`, проверяет `nginx -t`
  и перезагружает nginx только при изменениях.
- Если сертификата ещё нет, после обновления DNS и до деплоя nginx-конфига
  выпустить его на сервере:

```bash
certbot certonly --webroot -w /var/www/letsencrypt \
  -d finzdorovie.ru -d www.finzdorovie.ru
```

## Закрытые внутренние сервисы

В проде наружу должны смотреть только SSH и nginx:

- `22/tcp` — SSH;
- `80/tcp`, `443/tcp` — nginx;
- `10050/tcp` — Zabbix agent, если он нужен на сервере.

Postgres (`5432`) и Redis (`6379`) не публикуются на host-порты вообще. MinIO
слушает только `127.0.0.1:9000`, чтобы локальный nginx мог проксировать
presigned URL по `/partner-cabinet/`; консоль MinIO (`9001`) не публикуется.
DB, Redis и MinIO также вынесены в приватную Docker-сеть `internal: true`.
Дополнительно `deploy/firewall-lockdown.sh` ставит idempotent-правила `iptables`
и `ip6tables` для `INPUT` и `DOCKER-USER`: внешние подключения к
`5432/6379/9000/9001` блокируются даже при ошибке в облачном firewall или
случайной публикации Docker-порта.

`deploy.sh` после поднятия DB/Redis/MinIO запускает:

```bash
bash deploy/security-check.sh
```

Скрипт валит деплой, если `5432`, `6379`, `9000` или `9001` оказываются
опубликованы на внешний интерфейс. Ручная проверка на сервере:

```bash
cd /srv/personal_partner_account
docker compose -f docker-compose.prod.yml port db 5432
docker compose -f docker-compose.prod.yml port redis 6379
docker compose -f docker-compose.prod.yml port minio 9000
docker compose -f docker-compose.prod.yml port minio 9001
ss -ltnp | grep -E ':(5432|6379|9000|9001)\b' || true
```

Ожидаемо: у `db`, `redis`, `minio:9001` вывода нет; у `minio:9000` максимум
`127.0.0.1:9000`. В Selectel Cloud Firewall/security group дополнительно
оставить входящими только `22`, `80`, `443` и нужный мониторинг.

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
