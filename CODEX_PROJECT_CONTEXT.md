# Контекст проекта для Codex

Этот файл нужен, чтобы новый чат Codex быстро понял, что это за проект, где он
размещен и как с ним работать.

## Основные ссылки

- GitHub: https://github.com/raffaelo2016-svg/personal_partner_account
- Сайт: https://finzdorovie.ru
- Сайт с www: https://www.finzdorovie.ru
- Сервер Selectel: `161.104.52.194`
- SSH: `root@161.104.52.194`
- Папка проекта на сервере: `/srv/personal_partner_account`

## Что это за проект

Партнерский кабинет URITECH / ЮРИТЕХ для работы партнеров с клиентами.

В приложении есть две основные роли:

- партнер: личный кабинет, клиенты, задачи, документы, финансы, чат, обучение;
- администратор: управление партнерами, клиентами, настройками и данными.

Канонический вход один: `/login`.
После входа пользователь направляется по роли:

- партнер -> `/dashboard`;
- администратор -> `/admin`.

Маршрут `/` технически ведет на `/login`.

## Важные папки

- `frontend/` — клиентская часть приложения.
- `backend/` — API и серверная логика.
- `deploy/` — деплой, nginx, security-check, firewall scripts.
- `docs/` — решения и спецификации проекта.
- `Концепт/` — начальный макет/референс. Эта папка сейчас не в git и служит
  только как источник сравнения дизайна и логики.

## Продакшен

Домен `finzdorovie.ru` уже направлен на сервер:

- `A finzdorovie.ru -> 161.104.52.194`
- `A www.finzdorovie.ru -> 161.104.52.194`

TLS-сертификат Let's Encrypt выпущен для:

- `finzdorovie.ru`
- `www.finzdorovie.ru`

Nginx принимает внешний трафик на `80/443` и проксирует приложение.

## Безопасность сервера

В проде наружу должны быть доступны только:

- `22/tcp` — SSH;
- `80/tcp` — HTTP;
- `443/tcp` — HTTPS.

Postgres, Redis и MinIO не должны торчать наружу:

- Postgres `5432` — только внутри Docker;
- Redis `6379` — только внутри Docker;
- MinIO `9000` — только локально/внутри сервера;
- MinIO console `9001` — не публикуется.

Проверка безопасности:

```bash
cd /srv/personal_partner_account
bash deploy/security-check.sh
```

Ожидаемый результат: `[security] OK`.

## Деплой

Деплой настроен через GitHub Actions:

```text
.github/workflows/deploy.yml
```

Workflow должен запускаться при каждом push в `main`.

GitHub Actions подключается к серверу по SSH и выполняет:

```bash
cd /srv/personal_partner_account
git fetch origin main
git reset --hard origin/main
bash deploy/deploy.sh
```

Для автодеплоя в GitHub должны быть secrets:

```text
SSH_HOST=161.104.52.194
SSH_USER=root
SSH_PRIVATE_KEY=<private ssh key>
```

Если автодеплой не работает, первым делом проверить:

1. GitHub -> Actions -> Deploy to production.
2. Есть ли запуск на последний commit в `main`.
3. Лог шага `SSH and run deploy.sh`.
4. Наличие и правильность secrets.

## Ручной деплой на сервере

Если нужно обновить вручную:

```bash
ssh root@161.104.52.194
cd /srv/personal_partner_account
git fetch origin main
git reset --hard origin/main
bash deploy/deploy.sh
```

Проверка после деплоя:

```bash
curl http://127.0.0.1:8000/health
curl https://finzdorovie.ru/health
bash deploy/security-check.sh
```

## Серверный .env

Файл с секретами находится только на сервере:

```text
/srv/personal_partner_account/.env
```

Он не хранится в git и не должен коммититься.

Критичные переменные:

- `ENVIRONMENT=production`
- `COOKIE_SECURE=true`
- `ALLOWED_HOSTS=["finzdorovie.ru","www.finzdorovie.ru","localhost","127.0.0.1"]`
- `CORS_ORIGINS=["https://finzdorovie.ru","https://www.finzdorovie.ru"]`
- `S3_ENDPOINT=http://minio:9000`
- `S3_PUBLIC_ENDPOINT=https://finzdorovie.ru`
- `SECRET_KEY`, `DB_PASSWORD`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`,
  `MINIO_PASSWORD` — настоящие секреты, не дефолтные значения.

## Что уже недавно сделано

- Домен `finzdorovie.ru` привязан к серверу Selectel.
- Выпущен HTTPS-сертификат Let's Encrypt.
- Nginx настроен на домен и HTTPS.
- Закрыты публичные порты Postgres, Redis и MinIO.
- Добавлен security-check для проверки закрытых сервисов.
- Добавлен favicon в виде логотипной буквы `Ю`.
- В раздел обучения добавлены заглушки как в концепте:
  видеоинструкции, частые вопросы, важно, инструкции.

## Важные решения

- Единый вход: `/login`.
- Партнерский кабинет: `/dashboard`.
- Админка: `/admin`.
- Начальный концепт не является текущим приложением один в один, но полезен как
  визуальный и продуктовый референс.
- Если в текущем приложении что-то есть в концепте, но не видно на сайте, нужно
  сначала сравнить `Концепт/` и текущий `frontend/`, а потом предлагать правки.

## Быстрая проверка проекта локально

Frontend:

```bash
cd frontend
npm install
npm run build
```

Backend:

```bash
cd backend
poetry install
poetry run pytest
```

Если команды зависают или не дают вывода, не считать это успешной проверкой:
нужно отдельно смотреть логи и окружение.
