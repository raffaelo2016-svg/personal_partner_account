# Deploy — операционная справка

## SSH из среды ChatGPT Work — проверено 26.10.2026

В текущей среде прямой TCP отключён, а сетевой доступ идёт через управляемый
прокси. Обычный `ssh` не использует `ALL_PROXY` автоматически и завершается
`Operation not permitted` до аутентификации. Подключение через штатный SOCKS5
из `ALL_PROXY` проверено: сервер принимает существующий ключ, проверка ключа
сервера сохранена. Менять сетевые разрешения или настройки сервера не нужно.

Используйте обёртку, которая каждый раз читает актуальный временный порт прокси:

```bash
python3 deploy/remote_access.py ssh pwd
python3 deploy/remote_access.py ssh docker compose -f /srv/personal_partner_account/docker-compose.prod.yml ps
python3 deploy/remote_access.py upload local-file.py /tmp/local-file.py
python3 deploy/remote_access.py download /tmp/result.json result.json
```

Не фиксируйте порт прокси в SSH-конфигурации: он меняется между запусками.
Обёртка использует действующий управляемый прокси, а не отключает фильтрацию.
Если прокси вернёт отказ политики, это отдельный блокер: не обходите его и не
переходите к неуправляемым каналам. При `Operation not permitted` прямого SSH
сначала проверяйте штатный прокси, прежде чем просить пользователя запускать
команды вручную. На дату проверки `/health` отвечает успешно.

## Как работает деплой

### Удаление документов из карточки — 29.10.2026

Партнёр и администратор могут удалить документ: корзина рядом с файлом, подтверждение, тост. Удаление блокируется при `pending`/`processing` (409). Файл убирается из кабинета и MinIO; копия в Битрикс24 (Диск и таймлайн) остаётся по политике CRM.

- Интерфейс: `/srv/personal_partner_account/frontend/releases/delete-docs-20261029T144515Z`, симлинк `frontend/dist` переключён атомарно.
- Бэкенд: образы `backend`, `celery`, `celery-beat` пересобраны и пересозданы; rollback-теги `rollback-20261029t144254z`.
- Бэкап изменённых файлов: `/srv/backups/delete-docs-20261029T144254Z/files`.
- Миграция на сервере: `f7c2b8e14d90` (down_revision `c7e4a1b9d206`), таблица `file_deletion_tombstones`. В репозитории лежит та же миграция под `b6e2f4a90c17` (down_revision `a4e8f9c21d73`) — цепочки сервера и репозитория расходятся, при следующем полном деплое их нужно свести.
- Правки наложены точечно на серверные копии: `files.py`, `documents.py`, `models/__init__.py`, `ClientDetails.tsx`, `AdminDebtorDetails.tsx`, плюс новые `file_deletion_tombstone.py`, `f7c2b8e14d90_*.py`, `DocumentDeleteButton.tsx`. Незакоммиченные изменения репозитория не выкладывались.
- Проверено: `/health` 200, `/login` 200, новый `index-k0iej-jM.js`, чанк `DocumentDeleteButton-*.js` 200 и содержит тексты кнопки, `DELETE /api/v1/files/...` без токена — 403, таблица создана, celery и beat работают.

### Автоперевод браузера ломал чат — 29.10.2026

В `index.html` стоял `lang="en"`, поэтому Chrome считал русский кабинет
английским и запускал автоперевод. Переводчик переписывал текстовые узлы и
значения полей прямо в DOM: в отправку уходил перевод вместо напечатанного
текста, а подписи превращались в «остановка» (вместо «Техподдержка») и
«инфекционная задача» (вместо «Список задач»).

- Версия интерфейса: `/srv/personal_partner_account/frontend/releases/autotranslate-fix-20261029T122258Z`.
- Предыдущая версия: `/srv/personal_partner_account/frontend/releases/without-clients-fix-20261028T080200Z`.
- Резервная копия трёх изменённых файлов: `/srv/backups/autotranslate-20261029T122258Z/files`.
- Изменения: `index.html` — `lang="ru"` и `translate="no"` на `<html>`, `translate="no" class="notranslate"` на `#root`;
  `pages/Chat.tsx` и `pages/AdminChat.tsx` — `translate="no"` на сообщения, шапку чата, список чатов,
  поле ввода, поиск и имена вложений.
- Правки наложены на серверные копии точечно: они старее репозитория (нет `ChatDateSeparator`,
  кнопки удаления сообщения и новых лимитов файлов) — при слиянии сравните.
- Бандл собран на сервере с `VITE_API_URL=https://finzdorovie.ru/api/v1`; бэкенд, БД, миграции и nginx не менялись.
- Проверено: `/` отдаёт `<html lang="ru" translate="no">`, чанки `Chat`/`AdminChat` — 200, `/login` — 200, `/health` — 200.
- **В git правка пока не закоммичена.** До следующего штатного деплоя её нужно влить в `main`,
  иначе `git reset --hard origin/main` + сборка из репозитория вернут `lang="en"` и баг повторится.

### Партнёры без клиентов — 28.10.2026

На `finzdorovie.ru` опубликован экран «Партнёры без клиентов»: карточка «Нет
первого клиента» на дашборде стала ссылкой, а в разделе «Партнёры» появилась
кнопка «Без клиентов». На экране две вкладки — «Не рабочие» (активные партнёры
без единого клиента) и «Затихшие» (клиенты были, но последний — давно), с числом
дней без клиента и подсветкой: больше 30 дней — красным, больше 15 — синим.

- Версия интерфейса: `/srv/personal_partner_account/frontend/releases/without-clients-fix-20261028T080200Z`.
- Предыдущая версия: `/srv/personal_partner_account/frontend/releases/download-names-20261021T070214Z`.
- Резервная копия восьми изменённых файлов: `/srv/backups/without-clients-20261028T075419Z/files`,
  прежний образ backend помечен тегом `personal_partner_account-backend:rollback-before-without-clients`.
- Изменения: `backend/app/{api/admin_partners.py,schemas/partner.py,services/partner_service.py}`,
  `frontend/src/app/{routes.tsx,api/partners.ts,hooks/usePartners.ts,pages/AdminDashboard.tsx,pages/AdminPartners.tsx}`
  и два новых файла — `pages/AdminPartnersWithoutClients.tsx`, `utils/partnerPause.ts`.
- Правки наложены на серверные копии точечно, чтобы не затереть несохранённые в git
  хотфиксы (`todayInMoscow`, `RouteErrorPage`, `moscow_today`). Локальная рабочая
  копия от серверной в этих файлах отличается — при следующем слиянии сравните.
- Пройдены `tsc --noEmit` и production-сборка на сервере; обновлён только контейнер backend
  (БД, nginx и celery не менялись), миграции не требовались.
- После публикации проверены `/health`, публичный `index.html`, доступность чанка страницы,
  ответ эндпоинта изнутри контейнера: `no_clients` — 25, `stalled` — 13, что совпало
  с числом на карточке дашборда.
- **Инцидент 08:00 UTC:** первая сборка (`without-clients-20261028T075505Z`) ушла без
  `VITE_API_URL` и обращалась к `http://localhost:8000/api/v1` — вход и все запросы
  падали с «сервер недоступен». Сборка пересобрана с
  `VITE_API_URL=https://finzdorovie.ru/api/v1` (как в `deploy.sh:97`), симлинк
  переключён на `without-clients-fix-20261028T080200Z`; неверная сборка убрана
  в `/srv/backups/without-clients-20261028T075419Z/broken-release-no-api-url`.
  **Собирать фронт только с явным `VITE_API_URL`** — в `frontend/` нет `.env.production`,
  и без переменной Vite подставляет localhost.

Откат: вернуть симлинк `frontend/dist` на `download-names-20261021T070214Z`,
вернуть тег `rollback-before-without-clients` на `latest` и выполнить
`docker compose -f docker-compose.prod.yml up -d backend`, файлы восстановить из бэкапа.

### Сохранение названия скачиваемого документа — 21.10.2026

На `finzdorovie.ru` опубликовано исправление: при сохранении документа
браузер получает исходное имя с кириллицей и расширением вместо UUID хранилища.
Имена передаются в подписанном `Content-Disposition` и в кнопках скачивания
кабинетов партнёра и администратора. Исправление действует и для старых файлов
после обновления страницы; просмотр PDF в браузере сохраняется.

- Пакет, точный diff, проверки и скрипт с откатом: `output/download-names-release/`.
- Версия интерфейса: `/srv/personal_partner_account/frontend/releases/download-names-20261021T070214Z`.
- Предыдущая версия: `/srv/personal_partner_account/frontend/releases/region-20261020T092107Z`.
- Резервная копия исходников, прежний образ и результаты: `/srv/uritech-download-names-releases/20261021T070214Z/`.
- Пакет содержит только `backend/app/services/s3_service.py`, `backend/app/api/files.py`
  и изменение атрибута `download` в серверных `ClientDetails.tsx` / `AdminDebtorDetails.tsx`.
- Пройдены TypeScript, production-сборка, 6 серверных тестов в новом образе
  и импорт приложения. Обновлён только контейнер backend; БД, nginx и фоновые
  обработчики не менялись.
- После публикации проверены `/health`, публичные файлы интерфейса, контрольные
  суммы работающего backend и скачивание синтетического PDF через публичный
  MinIO URL: имя на русском сохранено, содержимое совпадает. Тестовый объект удалён.
- До публикации в Chrome проверено предложенное имя для PDF, ZIP и DOCX;
  непосредственная проверка на Windows не проводилась.

Обновление применено без commit/push/reset. Перед стандартным деплоем включите
этот пакет вместе с предыдущими точечными обновлениями в репозиторий.

### Поиск региона при вводе — 20.10.2026

На `finzdorovie.ru` опубликован поиск региона непосредственно в поле ввода
в обоих вариантах формы клиента. Поиск работает по части названия; выбор —
мышью или стрелками и Enter. После выбора сохраняется штатная подстановка суда.

- Пакет, контрольные суммы и diff: `output/region-release/`.
- Действующая версия интерфейса: `/srv/personal_partner_account/frontend/releases/region-20261020T092107Z`.
- Предыдущая версия: `/srv/personal_partner_account/frontend/releases/sro-20261020T090611Z`.
- Резервная копия исходников и результаты установки: `/srv/uritech-region-releases/20261020T092107Z/`.
- Перед переключением прошли 8 тестов `CustomSelect`, полная проверка TypeScript
  и production-сборка. После переключения проверены публичные файлы и `/health`.
- В отдельном браузере на опубликованном интерфейсе с подменой API тестовыми
  данными проверены «белг» → Белгородская область → Enter → суд А08, а также
  «моск» → Москва / Московская область → выбор мышью во второй форме клиента.
- Пакет включает только `CustomSelect.tsx`, его тесты и изменение двух полей
  в текущей серверной версии `ClientForm.tsx`; остальные серверные изменения сохранены.

Обновление применено без commit/push/reset. Перед стандартным деплоем включите
этот пакет вместе с предыдущими точечными обновлениями в репозиторий.

### Точечное обновление СРО — 20.10.2026

На `finzdorovie.ru` опубликованы карточка «СРО для заявления в суд» над
новостями, пункт меню и страница `/dashboard/sro` с реквизитами «ПроРешение».
Пакет содержит шесть файлов интерфейса и подготовлен поверх серверных
исходников, с сохранением действующих проверок ролей и обработки ошибок.
Backend, БД и nginx не изменялись.

- Пакет, контрольные суммы и точный diff: `output/sro-release/`.
- Действующая версия интерфейса: `/srv/personal_partner_account/frontend/releases/sro-20261020T090611Z`.
- Предыдущая версия: `/srv/personal_partner_account/frontend/releases/zip-size-20261016T082518Z`.
- Резервная копия исходников и результаты установки: `/srv/uritech-sro-releases/20261020T090611Z/`.
- Проверены серверная сборка, публичные JS/CSS, `/health`, переход в раздел
  СРО и точное содержимое буфера обмена. Проверка опубликованного интерфейса
  выполнялась в отдельном браузере с подменой API тестовыми данными.

Обновление применено без commit/push/reset. Перед следующим стандартным
деплоем со сбросом на `origin/main` включите этот пакет и предыдущие
точечные изменения в репозиторий, иначе они будут заменены старой версией.

### Стандартный процесс

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
