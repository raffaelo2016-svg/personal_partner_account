#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/srv/personal_partner_account
BACKUP_DIR=/srv/backups
BACKUP_KEEP=7
COMPOSE="docker compose -f docker-compose.prod.yml"

cd "$APP_DIR"

# Примечание: git fetch + reset --hard origin/main выполняются в workflow
# до запуска этого скрипта, чтобы избежать self-update проблемы
# (bash грузит весь скрипт в память до выполнения).

# Логгим команду, на которой скрипт упадёт.
trap 'status=$?; echo "[deploy.sh] failed on line $LINENO (exit=$status): ${BASH_COMMAND}" >&2' ERR

echo "[0/6] Lock down protected service ports"
bash deploy/firewall-lockdown.sh

echo "[1/6] Build backend images"
$COMPOSE build backend celery celery-beat

echo "[2/6] Ensure DB/Redis/MinIO are up"
$COMPOSE up -d --force-recreate db redis minio
COMPOSE="$COMPOSE" bash deploy/security-check.sh

echo "[storage] MinIO loopback endpoint"
storage_ok=0
for i in {1..15}; do
  if curl -fsS --max-time 5 http://127.0.0.1:9000/minio/health/live >/dev/null 2>&1; then
    echo "  OK (attempt $i)"
    storage_ok=1
    break
  fi
  sleep 2
done
if [ "$storage_ok" != "1" ]; then
  echo "MinIO loopback endpoint failed — file downloads through nginx would return 502." >&2
  $COMPOSE logs --tail=80 minio >&2 || true
  exit 1
fi

echo "[3/6] Backup database before migrations"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/$(date -u +%Y-%m-%d_%H-%M-%S).sql.gz"
# Ждём здоровья БД (в первый запуск up -d может занять пару секунд)
for i in {1..15}; do
  $COMPOSE exec -T db pg_isready -U app -d partner_cabinet >/dev/null 2>&1 && break
  sleep 2
done
$COMPOSE exec -T db pg_dump -U app partner_cabinet | gzip > "$BACKUP_FILE"
echo "  saved: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
# Ротация: оставляем последние N
ls -1t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +$((BACKUP_KEEP + 1)) | xargs -r rm -f

echo "[4/6] Run migrations"
$COMPOSE run --rm backend alembic upgrade head
# Подчищаем возможные «…-backend-run-*» сироты от прерванных прогонов —
# иначе следующий `up -d` запутается в именах и может не поднять backend.
docker ps -a --filter "name=personal_partner_account-backend-run-" --format '{{.ID}}' \
  | xargs -r docker rm -f >/dev/null 2>&1 || true

echo "[5/6] Recreate backend + celery (новый образ из шага 1 подхватится автоматически)"
# Без --force-recreate: после `compose build` digest образа поменялся,
# и `up -d` сам пересоздаст контейнеры. --force-recreate здесь лишний и
# раньше вызывал рейс с ещё не завершённым `compose run --rm` из шага 4.
# --wait блокирует до healthy (у backend есть healthcheck в compose-файле).
# timeout 120s покрывает start_period 20s + interval 15s × retries 5 в
# docker-compose.prod.yml::backend.healthcheck.
$COMPOSE up -d --wait --wait-timeout 120 backend celery celery-beat

echo "[health] backend /health"
ok=0
for i in {1..15}; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "  OK (attempt $i)"
    ok=1
    break
  fi
  sleep 2
done
if [ "$ok" != "1" ]; then
  echo "Backend health failed after restart — не публикую фронт и nginx-конфиги, старая версия продолжит обслуживать." >&2
  $COMPOSE logs --tail=80 backend >&2 || true
  exit 1
fi

echo "[bitrix] Ensure task event and safe initial responsible mappings"
if ! $COMPOSE exec -T backend python -m app.integrations.bitrix24.task_setup_cli \
  --apply --fill-missing-with-installer; then
  echo "  warning: Bitrix24 task activation was deferred; background sync remains safe" >&2
fi

echo "[bitrix] Ensure client deal fields and inbound event"
if ! $COMPOSE exec -T backend python -m app.integrations.bitrix24.client_setup_cli --apply; then
  echo "  warning: Bitrix24 client import activation was deferred; existing sync remains safe" >&2
fi

echo "[6/6] Build frontend"
cd frontend
npm ci
# Пробрасываем VITE_*-переменные из корневого .env в окружение билдера,
# чтобы Vite встроил их в бандл (client-side secrets — sitekey Yandex
# SmartCaptcha и т.п.). VITE_API_URL прибит гвоздями ниже.
if [ -f "$APP_DIR/.env" ]; then
  while IFS= read -r line; do
    case "$line" in
      VITE_*=*) export "$line" ;;
    esac
  done < "$APP_DIR/.env"
fi
# Собираем в отдельный каталог релиза и переключаем симлинк атомарно.
# Раньше сборка шла прямо в живой dist (симлинк), и пока vite перезаписывал
# файлы, nginx отдавал наполовину собранный каталог — часть ассетов 404.
# Теперь nginx в любой момент видит либо старый релиз целиком, либо новый.
RELEASE_NAME="release-$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE_DIR="releases/$RELEASE_NAME"
PREVIOUS_RELEASE="$(readlink dist || true)"
mkdir -p releases
npx tsc --noEmit
VITE_API_URL=https://finzdorovie.ru/api/v1 npx vite build --outDir "$RELEASE_DIR" --emptyOutDir
ln -sfn "$RELEASE_DIR" dist.new
mv -T dist.new dist
echo "  release: $RELEASE_DIR"
echo "  previous: ${PREVIOUS_RELEASE:-none} (для отката: ln -sfn <previous> dist.new && mv -T dist.new dist)"

# Старые релизы не удаляем автоматически: это точки отката. Только показываем,
# сколько их и сколько занимают — чистку делаем руками, осознанно.
RELEASES_COUNT="$(find releases -mindepth 1 -maxdepth 1 -type d | wc -l)"
RELEASES_SIZE="$(du -sh releases 2>/dev/null | cut -f1 || true)"
echo "  releases: ${RELEASES_COUNT} шт., ${RELEASES_SIZE}"
cd ..

echo "[nginx] Sync configs and reload if changed"
NGINX_CHANGED=0
install -d -m 755 /etc/nginx/snippets
for f in "$APP_DIR"/deploy/nginx/snippets/*.conf; do
  name="$(basename "$f")"
  if ! cmp -s "$f" "/etc/nginx/snippets/$name"; then
    install -m 644 "$f" "/etc/nginx/snippets/$name"
    NGINX_CHANGED=1
  fi
done
install -d -m 755 /etc/nginx/sites-available /etc/nginx/sites-enabled
if ! cmp -s "$APP_DIR/deploy/nginx/app.conf" /etc/nginx/sites-available/kobinetur; then
  install -m 644 "$APP_DIR/deploy/nginx/app.conf" /etc/nginx/sites-available/kobinetur
  NGINX_CHANGED=1
fi
[ -L /etc/nginx/sites-enabled/kobinetur ] || \
  ln -sf /etc/nginx/sites-available/kobinetur /etc/nginx/sites-enabled/kobinetur
if [ "$NGINX_CHANGED" = 1 ]; then
  nginx -t
  systemctl reload nginx
  echo "  nginx reloaded"
else
  echo "  nginx configs unchanged"
fi

echo "Deploy OK"
