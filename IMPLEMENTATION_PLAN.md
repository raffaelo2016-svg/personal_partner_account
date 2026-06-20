# План реализации: Партнёрский кабинет URITECH

## Оглавление

- [Анализ текущего состояния](#анализ-текущего-состояния)
- [Архитектура решения](#архитектура-решения)
- [Фаза 0 — Инфраструктура и подготовка](#фаза-0--инфраструктура-и-подготовка)
- [Фаза 1 — Ядро: Auth + CRUD Партнёры/Клиенты](#фаза-1--ядро-auth--crud-партнёрыклиенты)
- [Фаза 2 — Бизнес-логика: Статусы, Задачи, Прогресс](#фаза-2--бизнес-логика-статусы-задачи-прогресс)
- [Фаза 3 — Финансы и Документы](#фаза-3--финансы-и-документы)
- [Фаза 4 — Чат и Уведомления](#фаза-4--чат-и-уведомления)
- [Фаза 5 — Обучение, Настройки, Полировка](#фаза-5--обучение-настройки-полировка)
- [Инструкции для ИИ-агента](#инструкции-для-ии-агента)

---

## Анализ текущего состояния

### Что есть

| Артефакт | Описание | Готовность |
|----------|----------|------------|
| **Figma-фронтенд** | React 18 + Vite + TypeScript + Tailwind + shadcn/ui. 25 страниц, 48 UI-компонентов. Все данные захардкожены. | UI-макеты: 90%, логика: 0% |
| **PARTNER_CABINET_SPEC.md** | Подробная спецификация ~1500 строк: бизнес-логика, расчёты, навигация, пустые состояния для всех экранов | Полная |
| **Скриншоты** | 48 PNG-файлов — визуальные референсы для обоих кабинетов | Полная |

### Что отсутствует

- Бэкенд (API, база данных, авторизация)
- State management на фронтенде (всё на локальных `useState`)
- Подключение к реальному API (нет fetch/axios)
- Аутентификация и авторизация (JWT)
- Бизнес-логика на сервере (расчёты, статусы, переходы)
- Файловое хранилище (загрузка документов)
- Генерация документов (DOCX/PDF)
- Платёжная интеграция
- Чат (real-time)
- Уведомления (email, in-app)

### Что нужно зафиксировать до старта

В спецификации есть места, где AI может начать "додумывать" правила. Перед началом реализации нужно зафиксировать решения в отдельном decision log, иначе разные фазы поедут в разные стороны.

- **Единый логин и маршруты:** по спецификации вход один — `/login`, после него redirect по роли: партнёр → `/dashboard`, админ → `/admin`. Маршрут `/` должен только редиректить на `/login`. Отдельный `AdminLogin` в MVP не нужен.
- **Канонический route map:** партнёрские экраны живут под `/dashboard/...`, админские — под `/admin/...`. Внутренний индекс админа можно рендерить по `/admin`, а не требовать отдельную точку входа `/admin/dashboard`.
- **Словарь статусов и группировок:** нужен единый источник истины для `client.status`, групп статусов в фильтрах, цветов бейджей, отображаемых названий и правил попадания в карточки "До суда / Уже в суде / Завершено".
- **Формула баннера задолженности:** в спецификации есть противоречие ("Срок оплаты" vs "Количество дней просрочки"). До старта нужно утвердить точный расчёт `days_until_payment`, `overdue_days` и правила скрытия баннера.
- **Границы MVP:** платёжный шлюз, email-уведомления, AI-нейропомощник, резервные копии и журнал безопасности должны идти как integration-ready/stub, если заказчик отдельно не подтвердил full scope первой версии.

### Две роли, два интерфейса

```
┌─────────────────────────────────┐    ┌──────────────────────────────────┐
│    ПАРТНЁР (Partner)            │    │    АДМИН (URITECH)              │
│                                 │    │                                  │
│  /dashboard                     │    │  /admin                          │
│  ├── Дашборд                    │    │  ├── Дашборд (аналитика)         │
│  ├── Клиенты (CRUD)             │    │  ├── Партнёры (CRUD)             │
│  ├── Добавить клиента           │    │  ├── Все клиенты/должники        │
│  ├── Список задач               │    │  ├── Настройки системы           │
│  ├── Документы                  │    │  └── (Транзакции — расширение)   │
│  ├── Обучение                   │    │                                  │
│  ├── Чат                        │    │                                  │
│  └── Финансы (суд. расходы)     │    │                                  │
└─────────────────────────────────┘    └──────────────────────────────────┘
```

---

## Архитектура решения

### Целевой стек

```
Frontend (существует)         Backend (создать)              Инфра
─────────────────────         ───────────────────            ──────
React 18 + TypeScript         FastAPI (Python 3.12)          PostgreSQL 15+
Vite                          SQLAlchemy 2.0 + Alembic       Redis (кэш + очереди)
Tailwind CSS + shadcn/ui      Pydantic v2 (схемы)            MinIO / S3 (файлы)
React Router v7               JWT (access + refresh)         Docker Compose
Zustand (state mgmt)          Poetry (зависимости)
React Query / TanStack        Celery (фоновые задачи)
                              python-docx / WeasyPrint
                              WebSocket (чат)
```

### Структура проекта (целевая)

```
partner-cabinet/
├── frontend/                          # Существующий Figma-фронт (переименовать)
│   ├── src/
│   │   ├── app/
│   │   │   ├── api/                   # API-клиент (axios instances, endpoints)
│   │   │   │   ├── client.ts          # Базовый axios с interceptors
│   │   │   │   ├── auth.ts            # login, logout, refresh
│   │   │   │   ├── clients.ts         # CRUD клиентов
│   │   │   │   ├── tasks.ts           # CRUD задач
│   │   │   │   ├── finance.ts         # Судебные расходы, транзакции
│   │   │   │   ├── documents.ts       # Генерация, скачивание
│   │   │   │   ├── chat.ts            # WebSocket + REST
│   │   │   │   ├── admin.ts           # Все admin-эндпоинты
│   │   │   │   └── training.ts        # Видео, FAQ, инструкции
│   │   │   ├── store/                 # Zustand stores (ТОЛЬКО клиентское состояние)
│   │   │   │   ├── authStore.ts       # Токены, текущий пользователь, роль
│   │   │   │   └── uiStore.ts         # Модалки, сайдбар, тема
│   │   │   ├── hooks/                 # React Query hooks (ВСЕ серверные данные)
│   │   │   │   ├── useAuth.ts
│   │   │   │   ├── useClients.ts
│   │   │   │   ├── usePartners.ts     # Admin CRUD партнёров
│   │   │   │   ├── useTasks.ts
│   │   │   │   ├── useFinance.ts
│   │   │   │   ├── useDocuments.ts    # Генерация, список, скачивание
│   │   │   │   ├── useChat.ts
│   │   │   │   ├── useTraining.ts     # Видео, FAQ, инструкции
│   │   │   │   ├── useNotifications.ts # Колокольчик, список уведомлений
│   │   │   │   └── useDashboard.ts    # Дашборд партнёра и админа
│   │   │   ├── guards/                # Route protection
│   │   │   │   ├── AuthGuard.tsx
│   │   │   │   └── RoleGuard.tsx
│   │   │   ├── utils/                 # Утилиты
│   │   │   │   ├── formatMoney.ts     # kopecks → "15 000 ₽"
│   │   │   │   └── formatDate.ts      # ISO → локализованная дата (date-fns)
│   │   │   ├── components/            # Существующие + новые
│   │   │   ├── pages/                 # Существующие (рефакторинг)
│   │   │   ├── types.ts               # Расширить типы
│   │   │   └── routes.tsx             # Обернуть в guards
│   │   └── ...
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app, middleware, CORS
│   │   ├── config.py                  # Settings (Pydantic BaseSettings)
│   │   ├── database.py                # SQLAlchemy engine + session
│   │   ├── models/                    # SQLAlchemy ORM модели
│   │   │   ├── __init__.py            # Реэкспорт всех моделей (нужен Alembic!)
│   │   │   ├── base.py                # Base, TimestampMixin, SoftDeleteMixin
│   │   │   ├── enums.py               # StrEnum-ы (UserRole, ClientStatus, ...)
│   │   │   ├── user.py                # User (partner + admin)
│   │   │   ├── partner.py             # Partner profile
│   │   │   ├── client.py              # Client (debtor)
│   │   │   ├── client_status.py       # Status transitions log
│   │   │   ├── task.py                # Task
│   │   │   ├── document.py            # Document metadata
│   │   │   ├── file_upload.py         # FileUpload (загруженные файлы)
│   │   │   ├── finance.py             # CourtFee, Transaction
│   │   │   ├── chat.py                # ChatRoom, Message
│   │   │   ├── notification.py        # Notification
│   │   │   └── training.py            # Video, FAQ, Instruction
│   │   ├── schemas/                   # Pydantic schemas (request/response)
│   │   │   ├── pagination.py          # PaginatedResponse[T] (generic)
│   │   │   ├── auth.py
│   │   │   ├── partner.py
│   │   │   ├── client.py
│   │   │   ├── task.py
│   │   │   ├── document.py
│   │   │   ├── finance.py
│   │   │   ├── chat.py
│   │   │   ├── training.py            # TrainingVideo, FAQ, Instruction, ImportantNote
│   │   │   ├── notification.py        # Notification, NotificationPreference
│   │   │   └── admin.py
│   │   ├── api/                       # Роуты (APIRouter)
│   │   │   ├── auth.py                # POST /auth/login, /auth/refresh, /auth/logout
│   │   │   ├── partners.py            # CRUD партнёров (admin)
│   │   │   ├── clients.py             # CRUD клиентов (partner + admin)
│   │   │   ├── tasks.py               # CRUD задач
│   │   │   ├── documents.py           # Генерация + CRUD
│   │   │   ├── finance.py             # Судебные расходы, транзакции
│   │   │   ├── chat.py                # REST + WebSocket
│   │   │   ├── training.py            # Видео, FAQ
│   │   │   ├── admin.py               # Дашборд, статистика, настройки
│   │   │   ├── upload.py              # Загрузка файлов
│   │   │   └── notifications.py       # In-app нотификации
│   │   ├── services/                  # Бизнес-логика
│   │   │   ├── auth_service.py
│   │   │   ├── client_service.py      # Статус-машина, прогресс
│   │   │   ├── document_service.py    # Генерация DOCX/PDF
│   │   │   ├── finance_service.py     # Расчёт задолженностей
│   │   │   ├── task_service.py        # Дедлайны, автозадачи
│   │   │   ├── chat_service.py        # Сообщения + AI нейропомощник
│   │   │   └── notification_service.py
│   │   ├── core/                      # Инфраструктура
│   │   │   ├── security.py            # JWT encode/decode, password hashing
│   │   │   ├── dependencies.py        # get_current_user, get_db, role checks
│   │   │   ├── exceptions.py          # Кастомные HTTP exceptions
│   │   │   └── permissions.py         # RBAC декораторы
│   │   ├── celery_app.py              # Celery + Beat расписание
│   │   ├── scripts/                   # Скрипты (seed и т.д.)
│   │   │   └── seed.py
│   │   ├── tasks/                     # Celery tasks (подхватываются через autodiscover_tasks)
│   │   │   ├── __init__.py            # пустой файл (таски находятся через autodiscover)
│   │   │   ├── overdue_tasks.py       # @celery.task def check_overdue_tasks(): ...
│   │   │   └── overdue_fees.py        # @celery.task def check_overdue_court_fees(): ...
│   │   └── templates/                 # Шаблоны DOCX для генерации документов
│   ├── alembic/                       # Миграции (рядом с app/, не внутри)
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/
│   ├── pyproject.toml              # Poetry: зависимости + настройки проекта
│   ├── poetry.lock                 # Lockfile (автогенерируется)
│   ├── alembic.ini
│   └── Dockerfile
│
├── docker-compose.yml                 # PostgreSQL + Redis + MinIO + Backend
├── .env.example
├── Makefile                           # dev, migrate, test, seed (команды через poetry run)
└── IMPLEMENTATION_PLAN.md             # Этот файл
```

### ER-диаграмма (основные сущности)

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│   User   │────>│   Partner    │────>│    Client     │
│----------│  1:1│--------------│  1:N│--------------  │
│ id       │     │ id           │     │ id            │
│ email    │     │ user_id (FK) │     │ partner_id FK │
│ password │     │ company_name │     │ type          │
│ role     │     │ director     │     │ status        │
│ is_active│     │ inn          │     │ full_name     │
│          │     │ phone        │     │ case_number   │
│          │     │ court_fee    │     │ court_date    │
│          │     │ payment_days │     │ ...fields     │
└──────────┘     └──────────────┘     └───────┬───────┘
                                              │
              ┌───────────────────────────────┼──────────────────┐
              │                               │                  │
     ┌────────▼───────┐           ┌───────────▼──────┐  ┌───────▼────────┐
     │     Task       │           │   ClientStatus   │  │   CourtFee     │
     │ ──────────     │           │   ────────────   │  │   ──────────   │
     │ id             │           │ id               │  │ id             │
     │ client_id FK   │           │ client_id FK     │  │ client_id FK   │
     │ title          │           │ stage (1-5)      │  │ amount         │
     │ description    │           │ sub_status       │  │ status         │
     │ status         │           │ changed_at       │  │ due_date       │
     │ priority       │           │ changed_by       │  │ paid_at        │
     │ assigned_to    │           └──────────────────┘  └────────────────┘
     │ due_date       │
     └────────────────┘

     ┌───────────────┐     ┌───────────────┐     ┌────────────────┐
     │   Document    │     │   ChatRoom    │     │  Notification  │
     │ ─────────     │     │ ─────────     │     │ ────────────   │
     │ id            │     │ id            │     │ id             │
     │ client_id FK  │     │ partner_id FK │     │ user_id FK     │
     │ type          │     │ type          │     │ type           │
     │ status        │     │ ──────────    │     │ title          │
     │ file_path     │     │   Message     │     │ message        │
     │ generated_at  │     │   sender_id   │     │ is_read        │
     └───────────────┘     │   text        │     └────────────────┘
                           │   created_at  │
                           └───────────────┘
```

### Принципы реализации для Opus 4.6

- **Contract-first:** перед кодом каждой крупной фичи зафиксировать request/response-схемы и коды ошибок. Opus не должен "придумывать" поля по ходу реализации.
- **Traceability:** каждый экран из `PARTNER_CABINET_SPEC.md` должен быть связан с маршрутом, API, сущностями, пустым состоянием и критериями готовности.
- **Decision log:** все спорные бизнес-правила складывать в `docs/DECISIONS.md` в формате "Вопрос / Решение / Почему / Кто подтвердил". Если подтверждения нет — не реализовывать спорную логику как финальную.
- **MVP-first:** сначала довести до production-ready core flow: login, партнёры, клиенты, статусы, задачи, финансы, документы. AI-чат, email, backup automation и внешние платёжные провайдеры — после стабилизации ядра.

---

## Фаза 0 — Инфраструктура и подготовка

**Цель:** Развернуть рабочее окружение, создать скелет бэкенда, подключить фронт к API.

### Предусловие к фазе 0

Перед любым кодом создать `docs/DECISIONS.md` и зафиксировать в нём:

1. Канонические маршруты (`/login`, `/dashboard`, `/admin` и вложенные пути).
2. Канонический список бизнес-статусов клиента, групп фильтров и цветов UI.
3. Формулу расчёта судебных расходов, просрочки и баннера задолженности.
4. Что входит в MVP, а что идёт как stub/integration-ready.
5. Какие поля относятся к чувствительным ПДн и какие ограничения на их отображение в UI.

### Первый запуск (после выполнения фазы 0)

Краткий сценарий для проверки окружения:

```bash
# 1. Клонирование / переход в каталог проекта
cd partner-cabinet

# 2. Переменные окружения
cp .env.example .env
# При необходимости отредактировать .env (DB_PASSWORD, SECRET_KEY и т.д.)

# 3. Инфраструктура и бэкенд
docker compose up -d
cd backend && poetry install && poetry run alembic upgrade head && poetry run python -m app.scripts.seed
cd ..

# 4. Фронтенд (в отдельном терминале или после бэкенда)
cd frontend && npm install && npm run dev

# 5. Открыть в браузере
# http://localhost:5173 — логин: admin@uritech.ru / admin123 (админ) или тестовый партнёр из seed
```

Бэкенд без Docker: `make install`, `make migrate`, `make seed`, `make dev`. Фронт: `make dev-frontend` или `cd frontend && npm run dev`.

### Задача 0.0 — Реструктуризация проекта и Git

Текущая структура использует папки с кириллицей и пробелами (`Партнерский кабинет/`, `Кабинет/`), что ломает многие инструменты. Первый шаг — привести проект к стандартной структуре.

**Шаги:**

```bash
# 1. Инициализация git
git init
git branch -M main

# 2. Переименование папок
mv "Партнерский кабинет" frontend
mv "Кабинет" docs

# 3. Создать папку бэкенда
mkdir backend
```

**`.gitignore`:**
```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
dist/

# Poetry (poetry.lock коммитится — НЕ добавлять сюда)

# Node
node_modules/
frontend/node_modules/

# IDE
.idea/
.vscode/
*.swp
.DS_Store

# Env
.env
.env.local
.env.production

# Build
frontend/dist/
backend/build/

# Storage
uploads/
*.sqlite3
```

**`.env.example`:**
```env
# Database
DATABASE_URL=postgresql+asyncpg://app:secret@localhost:5432/partner_cabinet
DB_PASSWORD=secret

# Redis (также используется Celery как broker)
REDIS_URL=redis://localhost:6379/0

# Auth
SECRET_KEY=change-me-to-random-64-char-string
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# S3 / MinIO
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=partner-cabinet
MINIO_PASSWORD=minioadmin

# CORS
CORS_ORIGINS=["http://localhost:5173"]

# Logging
LOG_LEVEL=INFO

# Нейропомощник (фаза 4, опционально)
OPENAI_API_KEY=

# Frontend
VITE_API_URL=http://localhost:8000/api/v1
```

**Миграция `figma:asset` импортов:**

В файлах `Layout.tsx`, `AdminLayout.tsx`, `Login.tsx` есть Figma-специфичные импорты:
```ts
// БЫЛО (не работает в обычном Vite):
import logo from 'figma:asset/7df0f9f38de2640bb126cbdaf3174e64288ee1e0.png';

// СТАЛО:
import logo from '@/assets/logo.png';
```

Шаги:
1. Переименовать `frontend/src/assets/7df0f9f38de2640bb126cbdaf3174e64288ee1e0.png` → `frontend/src/assets/logo.png`
2. Заменить все `figma:asset/...` импорты на `@/assets/logo.png`
3. Настроить алиас `@` в `vite.config.ts`:
```ts
resolve: {
  alias: {
    '@': path.resolve(__dirname, './src'),
  },
}
```

**Результат:** Чистая структура `frontend/`, `backend/`, `docs/`, инициализированный git, рабочие импорты.

### Задача 0.1 — Инициализация бэкенда

**Файлы для создания:**

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   └── database.py
├── pyproject.toml
├── alembic.ini
└── Dockerfile
```

**Инициализация Poetry:**
```bash
cd backend
poetry init --name partner-cabinet-backend --python "^3.12"
```

**Основные зависимости (`poetry add`):**
```bash
poetry add fastapi "uvicorn[standard]" sqlalchemy alembic asyncpg \
  pydantic pydantic-settings PyJWT bcrypt \
  python-multipart boto3 python-docx weasyprint celery redis \
  websockets httpx structlog slowapi
```

**Dev-зависимости (`poetry add --group dev`):**
```bash
poetry add --group dev pytest pytest-asyncio pytest-cov httpx ruff mypy
```

**Результат — `pyproject.toml`:**
```toml
[tool.poetry]
name = "partner-cabinet-backend"
version = "0.1.0"
description = "Backend для партнёрского кабинета URITECH"
authors = ["URITECH"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.115"
uvicorn = {version = "^0.34", extras = ["standard"]}
sqlalchemy = "^2.0"
alembic = "^1.14"
asyncpg = "^0.30"
pydantic = "^2.10"
pydantic-settings = "^2.7"
PyJWT = "^2.10"
bcrypt = "^4.2"
structlog = "^24"
slowapi = "^0.1"
python-multipart = ">=0.0.12"
boto3 = "^1.36"
python-docx = "^1.1"
weasyprint = "^63"
celery = "^5.4"
redis = "^5.2"
websockets = "^14"
httpx = "^0.28"

[tool.poetry.group.dev.dependencies]
pytest = "^8"
pytest-asyncio = "^0.25"
pytest-cov = "^6"
httpx = "^0.28"
ruff = "^0.9"
mypy = "^1.14"

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
plugins = ["pydantic.mypy"]
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

**`Dockerfile` (multi-stage с Poetry):**
```dockerfile
FROM python:3.12-slim AS builder

ENV POETRY_VERSION=2.1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

FROM python:3.12-slim AS runtime

WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY . .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`models/base.py` — базовая модель (SQLAlchemy 2.0 DeclarativeBase):**
```python
import uuid
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Миксин для created_at / updated_at на всех моделях."""
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class SoftDeleteMixin:
    """Миксин для мягкого удаления. Используется на Client, Partner, Document."""
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
```

Все модели наследуют `Base` и `TimestampMixin`. Модели, которые нельзя жёстко удалять (`Client`, `Partner`, `Document`, `CourtFee`), также наследуют `SoftDeleteMixin`.

**`models/__init__.py` — обязательный реэкспорт всех моделей:**
```python
from app.models.base import Base
from app.models.user import User
from app.models.partner import Partner
from app.models.client import Client
from app.models.client_status import ClientStatusLog
from app.models.task import Task
from app.models.document import Document
from app.models.file_upload import FileUpload
from app.models.finance import CourtFee, Transaction
from app.models.chat import ChatRoom, ChatMessage
from app.models.notification import Notification
from app.models.training import TrainingVideo, FAQ, Instruction, ImportantNote
from app.models.settings import SystemSetting, NotificationPreference
```
Без этого файла Alembic не увидит модели при `--autogenerate`.

**`models/enums.py` — строковые Enum-ы для статусов:**
```python
from enum import StrEnum

class UserRole(StrEnum):
    PARTNER = "partner"
    ADMIN = "admin"

class ClientType(StrEnum):
    BEFORE_COURT = "before_court"
    IN_COURT = "in_court"

class ClientStatus(StrEnum):
    NEW = "new"
    DOCUMENTS_UPLOAD = "documents_upload"
    DOCUMENTS_GENERATION = "documents_generation"
    DOCUMENTS_VERIFICATION = "documents_verification"
    DOCUMENTS_READY = "documents_ready"
    PACKAGE_PREPARATION = "package_preparation"
    SENT_TO_COURT = "sent_to_court"
    WAITING_ACCEPTANCE = "waiting_acceptance"
    ACCEPTED_BY_COURT = "accepted_by_court"
    LEFT_WITHOUT_MOTION = "left_without_motion"
    RETURNED = "returned"
    REJECTED = "rejected"
    HEARING_SCHEDULED = "hearing_scheduled"
    HEARING_PREPARATION = "hearing_preparation"
    WAITING_HEARING = "waiting_hearing"
    COMPLETED = "completed"
    REJECTED_FINAL = "rejected_final"

class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"

class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class PartnerStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"

class CourtFeeStatus(StrEnum):
    UNPAID = "unpaid"
    PAID = "paid"
    OVERDUE = "overdue"

class TransactionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
```
Использовать `StrEnum` — значения сериализуются в JSON как строки автоматически. **В моделях** хранить статусы, роли, типы как строки (`Mapped[str]`, колонка `String(...)`), чтобы не привязывать ORM к enum. **В Pydantic-схемах** — использовать эти Enum из `app.models.enums` (или продублировать в `schemas/`) в полях request/response, чтобы API и фронт получали валидированные значения и автодокументацию OpenAPI.

**`schemas/pagination.py` — переиспользуемая схема пагинации:**
```python
from typing import Generic, TypeVar
from pydantic import BaseModel, Field
from fastapi import Query

T = TypeVar("T")

class PaginationParams:
    """Dependency для query-параметров пагинации. Использование: params: PaginationParams = Depends()"""
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Номер страницы"),
        page_size: int = Query(20, ge=1, le=100, description="Элементов на странице (макс. 100)"),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    pages: int
    page_size: int
```
Использование в роуте:
```python
@router.get("/clients", response_model=PaginatedResponse[ClientRead])
async def list_clients(params: PaginationParams = Depends(), ...):
    items, total = await client_service.get_list(offset=params.offset, limit=params.page_size, ...)
    return PaginatedResponse(items=items, total=total, page=params.page, pages=math.ceil(total / params.page_size), page_size=params.page_size)
```
`PaginationParams` как dependency гарантирует единообразие во всех list-эндпоинтах: `page` (default 1, min 1), `page_size` (default 20, min 1, max 100). Считает `offset` автоматически.

**`celery_app.py` — конфигурация Celery:**
```python
from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery = Celery("partner_cabinet", broker=settings.REDIS_URL)

# Автоподключение тасков из app.tasks — избегает circular import (tasks импортируют celery из app.celery_app)
celery.autodiscover_tasks(["app.tasks"])

celery.conf.beat_schedule = {
    "check-overdue-tasks": {
        "task": "app.tasks.overdue_tasks.check_overdue_tasks",
        "schedule": crontab(hour=1, minute=0),  # каждый день в 01:00
    },
    "check-overdue-court-fees": {
        "task": "app.tasks.overdue_fees.check_overdue_court_fees",
        "schedule": crontab(hour=1, minute=30),
    },
}
```
В каждом файле таска декорируется: `@celery.task` (импорт `celery` из `app.celery_app`).

**`main.py` — ключевые моменты:**
- CORS middleware с `allow_origins` из `config.CORS_ORIGINS`
- Подключение всех APIRouter с префиксами `/api/v1/...`
- Lifespan для startup/shutdown (DB connection pool)
- Exception handlers для кастомных ошибок
- Middleware для `structlog` (добавляет `request_id` к каждому запросу)
- `GET /health` — проверка доступности DB и Redis:
```json
{ "status": "ok", "db": "ok", "redis": "ok", "version": "0.1.0" }
```

**`config.py`:**
- `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- `S3_ENDPOINT`, `S3_BUCKET` (для MinIO/S3)
- `CORS_ORIGINS` (список)
- `LOG_LEVEL` (default: `"INFO"`)

**`database.py`:**
- `async_engine` + `async_sessionmaker`
- `get_db` dependency для FastAPI

**`core/dependencies.py` — ключевые dependencies:**
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Извлекает и валидирует пользователя из JWT-токена."""
    token = credentials.credentials
    payload = decode_access_token(token)  # из core/security.py; бросает 401 если невалидный/истёк
    user = await db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user

def require_role(*roles: str):
    """Dependency-factory для проверки роли. Использование: Depends(require_role("admin"))"""
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden", headers={"code": "FORBIDDEN"})
        return current_user
    return checker
```
Использование в роутах: `current_user: User = Depends(get_current_user)` для аутентифицированных эндпоинтов, `current_user: User = Depends(require_role("admin"))` для админских.

### Задача 0.2 — Docker Compose

```yaml
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: partner_cabinet
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d partner_cabinet"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD}
    # Без healthcheck: образ minio/minio не содержит mc/curl. Backend не ждёт готовности MinIO.

  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_started
    env_file: .env
    volumes:
      - ./backend/app:/app/app   # только код приложения; .venv из образа не затирается
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

  celery:
    build: ./backend
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file: .env
    volumes:
      - ./backend/app:/app/app
    command: ["celery", "-A", "app.celery_app", "worker", "--loglevel=info", "--beat"]
    restart: unless-stopped

volumes:
  pgdata:
```

> **Примечание:** В образе backend нет Poetry в runtime — только `.venv` из builder и `PATH=/app/.venv/bin:$PATH`. Поэтому команды — `uvicorn` и `celery` напрямую. Монтируется только `./backend/app` в `/app/app`, чтобы не затирать `.venv` из образа (иначе после mount контейнер остаётся без зависимостей). Frontend запускается **отдельно** через `cd frontend && npm run dev` (Vite на 5173). В docker-compose только инфра + бэкенд.

**`Makefile` (команды через Poetry):**
```makefile
.PHONY: install dev dev-frontend migrate seed test lint

install:
	cd backend && poetry install

dev:
	cd backend && poetry run uvicorn app.main:app --reload --port 8000

# Фронт запускается отдельно (второй терминал или параллельно)
dev-frontend:
	cd frontend && npm run dev

migrate:
	cd backend && poetry run alembic upgrade head

migrate-create:
	cd backend && poetry run alembic revision --autogenerate -m "$(msg)"

seed:
	cd backend && poetry run python -m app.scripts.seed

test:
	cd backend && poetry run pytest -v --cov=app

lint:
	cd backend && poetry run ruff check . && poetry run mypy app

format:
	cd backend && poetry run ruff format .
```

### Задача 0.3 — Подготовка фронтенда к интеграции

**Установить зависимости:**
```bash
npm install axios @tanstack/react-query zustand zod @hookform/resolvers date-fns
```
Примечание: `react-hook-form` уже установлен в проекте. `zod` — для валидации форм, `@hookform/resolvers` — адаптер zod для react-hook-form. `date-fns` — форматирование дат (соглашение: все даты из API в ISO 8601, форматирование только на фронте).

**Создать файлы:**

1. **`src/app/api/client.ts`** — axios instance:
   - `baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'`
   - Request interceptor: добавление `Authorization: Bearer <token>` из store
   - Response interceptor: при 401 → **одна общая очередь refresh** (один запрос выполняет refresh, остальные ждут тот же Promise и повторяют свой запрос с новым токеном; при неудаче refresh — logout для всех)
   - При 401 с `code: "TOKEN_EXPIRED"` — запуск refresh; при `code: "INVALID_CREDENTIALS"` — только logout, без refresh

2. **`src/app/store/authStore.ts`** — Zustand store:
   - `user`, `accessToken`, `refreshToken`, `role`
   - `login()`, `logout()`, `refreshTokens()`
   - Persist через `localStorage`

3. **`src/app/guards/AuthGuard.tsx`**:
   - Проверка наличия токена
   - Если нет → redirect на `/login`
   - Если есть → `<Outlet />`

4. **`src/app/guards/RoleGuard.tsx`**:
   - `props: { allowedRoles: ('partner' | 'admin')[] }`
   - Если роль не совпадает → redirect на соответствующий дашборд

5. **Обновить `routes.tsx`** — обернуть маршруты в guards:
   ```tsx
   {
     path: '/login',
     Component: Login,
   },
   {
     path: '/dashboard',
     element: <AuthGuard><RoleGuard allowedRoles={['partner']} /></AuthGuard>,
     Component: Layout,
     children: [...]
   },
   {
     path: '/admin',
     element: <AuthGuard><RoleGuard allowedRoles={['admin']} /></AuthGuard>,
     Component: AdminLayout,
     children: [...]
   }
   ```

6. **Нормализовать карту маршрутов:**
   - `/` → redirect на `/login`
   - убрать отдельный экран `AdminLogin.tsx` из боевого сценария
   - админский index route должен открывать `AdminDashboard` на `/admin`

7. **`QueryClientProvider`** — в корне приложения (например в `main.tsx` или `App.tsx`) обернуть роутер в `<QueryClientProvider client={queryClient}>`, инициализировать `QueryClient` с разумными `defaultOptions.queries` (например `staleTime: 60_000`). Без этого все `useQuery` падают с ошибкой.

### Задача 0.4 — Миграции и seed

- В каталоге `backend/` выполнить: `poetry run alembic init -t async alembic` — создаётся папка `backend/alembic/` (env.py, script.py.mako, versions/).
- В `alembic.ini` оставить `script_location = alembic`.
- Настроить `alembic/env.py`: импортировать `Base` и все модели из `app.models` (чтобы autogenerate их видел), подставить `DATABASE_URL` из `app.config.settings`.
- Первая миграция: `poetry run alembic revision --autogenerate -m "init users partners"`
- Применить: `poetry run alembic upgrade head`
- Seed-скрипт `backend/app/scripts/seed.py`:
  - Создать admin-пользователя (`admin@uritech.ru` / `admin123`)
  - Создать тестового партнёра с 3 клиентами
  - Для тестового партнёра создать 3 чат-комнаты (`arbitration_manager`, `assistant`, `ai_assistant`), чтобы при первом входе раздел «Чат» был доступен
  - Добавить 2–3 записи в раздел обучения: по одному видео, FAQ и инструкции (для проверки экрана «Обучение» без пустых списков)
  - **Идемпотентность:** при повторном запуске скрипт не должен падать. Проверять существование записей по ключу (email для User, уникальные идентификаторы для партнёра/комнат/обучения) и пропускать создание или обновлять существующие. Нужно для локальной разработки и CI.
  - Запуск: `poetry run python -m app.scripts.seed`

### Задача 0.5 — Базовое качество поставки: CI, observability, audit

Чтобы Opus 4.6 не просто "написал код", а довёл систему до рабочего состояния, в Phase 0 нужно заложить минимальную инженерную обвязку:

- **CI pipeline:** lint + backend tests + frontend build на каждый PR/merge.
- **OpenAPI как артефакт:** экспортировать актуальную схему API и проверять, что новые эндпоинты не ломают контракт молча.
- **Audit trail:** логировать критичные действия (`login`, `change_password`, `create_partner`, `create_client`, `change_status`, `create_payment`, `generate_document`).
- **Observability:** единый `request_id`, структурные логи, healthcheck, базовые метрики ошибок/латентности.
- **Rollback-friendly migrations:** принцип "одна логическая миграция = один PR", без смешивания схемы, seed и больших refactor-изменений.

---

## Фаза 1 — Ядро: Auth + CRUD Партнёры/Клиенты

**Цель:** Рабочая авторизация, партнёр может создавать/просматривать клиентов, админ управляет партнёрами.

### Задача 1.1 — Модель User + Auth API

**Backend:**

Модель `User` (наследует `Base` и `TimestampMixin` — created_at/updated_at из миксина):
```python
class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # 'partner' | 'admin'
    is_active: Mapped[bool] = mapped_column(default=True)
```

Эндпоинты:
- `POST /api/v1/auth/login` → `{ access_token, refresh_token, user: { id, email, role } }`
- `POST /api/v1/auth/refresh` → `{ access_token }`
- `POST /api/v1/auth/logout` → revoke refresh token (хранить в Redis)
- `GET /api/v1/auth/me` → текущий пользователь

Security:
- `bcrypt` (напрямую, без passlib) для хеширования паролей
- `PyJWT` (HS256): access_token (15 мин), refresh_token (7 дней)
- Refresh tokens в Redis с TTL
- **Не использовать** `python-jose` (заброшен) и `passlib` (заброшен)
- **Rate limiting** через `slowapi`: `POST /auth/login` — max 5 запросов/минуту на IP, `POST /auth/register` — max 3 запросов/минуту на IP. При превышении → HTTP 429 `Too Many Requests`
- **Политика паролей:** минимум 8 символов при регистрации и смене пароля. Проверка на бэкенде (Pydantic min_length=8). Усложнение (цифры/спецсимволы) — по желанию, не обязательно на первом этапе.

**Frontend:**

- Переделать `Login.tsx`: `handleSubmit` → вызов `POST /auth/login`, сохранение в authStore, redirect по роли
- Убрать `AdminLogin.tsx` из боевого потока; оставить только если нужен временный legacy-redirect
- Объединить login-flow: один маршрут `/login`, после входа redirect по `user.role`
- `/` сделать техническим редиректом на `/login`
- Убрать хардкод `navigate('/dashboard')` — заменить на роутинг по роли

### Задача 1.2 — Модель Partner + Admin CRUD

**Backend:**

Модель `Partner` (наследует `Base`, `TimestampMixin`, `SoftDeleteMixin`; в выборках фильтровать по `deleted_at.is_(None)`):
```python
class Partner(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "partners"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    company_name: Mapped[str] = mapped_column(String(255))
    director_name: Mapped[str] = mapped_column(String(255))
    inn: Mapped[str] = mapped_column(String(12))
    phone: Mapped[str] = mapped_column(String(20))
    court_fee_per_client: Mapped[int] = mapped_column(default=1_500_000)  # в копейках (15 000 ₽)
    payment_term_days: Mapped[int] = mapped_column(default=10)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | active | blocked
```

Эндпоинты (admin-only):
- `GET /api/v1/admin/partners` — список с фильтрами (search, status, date_from, date_to, pagination)
- `GET /api/v1/admin/partners/{id}` — детальная карточка
- `POST /api/v1/admin/partners` — создание (+ создание User с ролью partner)
- `PUT /api/v1/admin/partners/{id}` — обновление
- `GET /api/v1/admin/partners/stats` — статистика (активные, всего клиентов, должников за период)

**Frontend:**

- `AdminPartners.tsx`: заменить хардкод на `useQuery('partners', fetchPartners)`
- `AdminAddPartner.tsx`: подключить `useMutation` для создания
- `AdminPartnerDetails.tsx`: загружать данные по ID из URL

### Задача 1.3 — Модель Client + CRUD

**Backend:**

Модель `Client` (наследует `Base`, `TimestampMixin`, `SoftDeleteMixin`; в выборках фильтровать по `deleted_at.is_(None)`):
```python
class Client(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "clients"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"), index=True)
    type: Mapped[str] = mapped_column(String(20), index=True)  # before_court | in_court
    status: Mapped[str] = mapped_column(String(50), default="new", index=True)
    
    # Персональные данные
    full_name: Mapped[str] = mapped_column(String(255))
    date_of_birth: Mapped[Optional[date]]
    passport_series: Mapped[Optional[str]] = mapped_column(String(4))
    passport_number: Mapped[Optional[str]] = mapped_column(String(6))
    passport_issue_date: Mapped[Optional[date]]
    passport_issued_by: Mapped[Optional[str]] = mapped_column(String(500))
    registration_address: Mapped[Optional[str]] = mapped_column(String(500))
    inn: Mapped[Optional[str]] = mapped_column(String(12))
    snils: Mapped[Optional[str]] = mapped_column(String(14))
    
    # Контакты
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Юридическая инфо
    region: Mapped[Optional[str]] = mapped_column(String(100))
    arbitrage_court: Mapped[Optional[str]] = mapped_column(String(255))
    case_number: Mapped[Optional[str]] = mapped_column(String(50))
    court_procedure_date: Mapped[Optional[date]]  # дата назначения процедуры
```

Эндпоинты (для партнёра):
- `GET /api/v1/clients` — список с фильтрами (search, type, status, pagination). Автоматически фильтрует по `partner_id` текущего пользователя
- `GET /api/v1/clients/{id}` — карточка клиента (только свой)
- `POST /api/v1/clients` — создание
- `PUT /api/v1/clients/{id}` — обновление
- `GET /api/v1/clients/stats` — статистика для дашборда (всего, до суда, в суде, завершённых)

Эндпоинты (для админа):
- `GET /api/v1/admin/clients` — все клиенты всех партнёров
- `GET /api/v1/admin/clients/{id}` — карточка любого клиента
- `PUT /api/v1/admin/clients/{id}` — обновление (в т.ч. court_procedure_date)

**Frontend:**

- `ClientsList.tsx`: заменить моки на `useQuery` + реальные фильтры
- `ClientForm.tsx`: `useMutation(createClient)`, redirect после успеха
- `ClientDetails.tsx`: `useQuery(getClient, id)`, отображение реальных данных
- `AdminClients.tsx`: подключить к admin-эндпоинту

### Задача 1.4 — Загрузка файлов

**Backend:**

- `POST /api/v1/upload` — загрузка файла в MinIO/S3, возврат `{ file_id, url, filename, size }`
- Модель `FileUpload` в `models/file_upload.py` (id, client_id, document_type, original_name, s3_key, size, mime_type, uploaded_at); наследует `Base`, `TimestampMixin`. Реэкспорт в `models/__init__.py`.
- `GET /api/v1/files/{file_id}` — получение pre-signed URL
- `DELETE /api/v1/files/{file_id}` — удаление

Валидация загружаемых файлов (без python-magic — только белый список расширений и Content-Type):
```python
UPLOAD_MAX_SIZE_MB = 10
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
```
- Проверять `Content-Length` до чтения тела (отклонять > 10 МБ сразу, HTTP 413, код `FILE_TOO_LARGE`)
- Проверять расширение файла по белому списку и совпадение с заявленным `Content-Type` (HTTP 415, код `UNSUPPORTED_FILE_TYPE`). Определение MIME по содержимому (python-magic) — техдолг при необходимости.
- Генерировать случайный `s3_key` (UUID), не использовать оригинальное имя файла в пути (безопасность)

**Frontend:**

- `ClientForm.tsx`: подключить реальный upload через `api/upload`, отображать прогресс загрузки
- Клиентская пред-валидация: размер и расширение файла до отправки

### Задача 1.5 — Регистрация партнёра

**Backend:**

- `POST /api/v1/auth/register` — регистрация нового партнёра (создание User + Partner со статусом `pending`)
- После регистрации: уведомление админу о новом партнёре на модерацию

**Frontend:**

- `Registration.tsx`: подключить к `POST /auth/register`

---

## Фаза 2 — Бизнес-логика: Статусы, Задачи, Прогресс

**Цель:** Реализовать статус-машину клиента, систему задач и прогресс-бар.

### Задача 2.1 — Статус-машина клиента

**Backend:**

Определить все допустимые переходы между статусами (использовать `ClientStatus` из `models.enums`):

```python
from app.models.enums import ClientStatus

STATUS_TRANSITIONS: dict[ClientStatus, list[ClientStatus]] = {
    ClientStatus.NEW: [ClientStatus.DOCUMENTS_UPLOAD],
    ClientStatus.DOCUMENTS_UPLOAD: [ClientStatus.DOCUMENTS_GENERATION],
    ClientStatus.DOCUMENTS_GENERATION: [ClientStatus.DOCUMENTS_VERIFICATION],
    ClientStatus.DOCUMENTS_VERIFICATION: [ClientStatus.DOCUMENTS_READY, ClientStatus.DOCUMENTS_GENERATION],
    ClientStatus.DOCUMENTS_READY: [ClientStatus.PACKAGE_PREPARATION],
    ClientStatus.PACKAGE_PREPARATION: [ClientStatus.SENT_TO_COURT],
    ClientStatus.SENT_TO_COURT: [ClientStatus.WAITING_ACCEPTANCE],
    ClientStatus.WAITING_ACCEPTANCE: [
        ClientStatus.ACCEPTED_BY_COURT,
        ClientStatus.LEFT_WITHOUT_MOTION,
        ClientStatus.RETURNED,
        ClientStatus.REJECTED,
    ],
    ClientStatus.LEFT_WITHOUT_MOTION: [ClientStatus.DOCUMENTS_GENERATION],
    ClientStatus.RETURNED: [ClientStatus.DOCUMENTS_GENERATION],
    ClientStatus.ACCEPTED_BY_COURT: [ClientStatus.HEARING_SCHEDULED],
    ClientStatus.HEARING_SCHEDULED: [ClientStatus.HEARING_PREPARATION],
    ClientStatus.HEARING_PREPARATION: [ClientStatus.WAITING_HEARING],
    ClientStatus.WAITING_HEARING: [ClientStatus.COMPLETED, ClientStatus.REJECTED_FINAL],
}
```
При проверке перехода: текущий статус и целевой приводить к enum (если в БД хранятся строки — использовать `ClientStatus(current)`).

Модель `ClientStatusLog`:
```python
class ClientStatusLog(Base):
    __tablename__ = "client_status_logs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"))
    from_status: Mapped[str] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50))
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[Optional[str]]
    changed_at: Mapped[datetime] = mapped_column(default=func.now())
```

Сервис `ClientService`:
- `change_status(client_id, new_status, user_id)` — валидация перехода + запись в лог
- `get_progress(client_id)` — расчёт % прогресса по этапам

Эндпоинт:
- `POST /api/v1/clients/{id}/status` → `{ status: "new_status", comment?: "..." }`
- `GET /api/v1/clients/{id}/status-history` → список переходов

### Задача 2.2 — Прогресс-бар (`ClientProgress`)

**Backend:**

- `GET /api/v1/clients/{id}/progress` — возвращает:
```json
{
  "overall_percent": 45,
  "stages": [
    {
      "id": 1,
      "title": "Сбор документов",
      "status": "completed",
      "sub_steps": [
        { "title": "Загрузка документов", "status": "completed", "completed_at": "..." }
      ]
    },
    {
      "id": 2,
      "title": "Формирование документов",
      "status": "in_progress",
      "sub_steps": [
        { "title": "Генерация документов", "status": "in_progress" },
        { "title": "Проверка документов", "status": "pending" },
        { "title": "Документы готовы", "status": "pending" }
      ]
    }
  ]
}
```

Логика расчёта:
- Каждый подэтап = 1 единица
- Всего подэтапов = сумма по всем этапам
- `overall_percent = completed_sub_steps / total_sub_steps * 100`

**Frontend:**

- `ClientProgress.tsx`: заменить хардкод на данные из `GET /clients/{id}/progress`

### Задача 2.3 — Задачи (Tasks)

**Backend:**

Модель `Task` (наследует `Base`, `TimestampMixin`):
```python
class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending | in_progress | completed | overdue
    priority: Mapped[str] = mapped_column(String(10), default="medium")  # low | medium | high
    assigned_to: Mapped[str] = mapped_column(String(20))  # partner | uritech
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date] = mapped_column(index=True)
    completed_at: Mapped[Optional[datetime]]
```

Эндпоинты:
- `GET /api/v1/tasks` — с фильтрами (status, priority, assigned_to, search, pagination)
- `POST /api/v1/tasks` — создание
- `PUT /api/v1/tasks/{id}` — обновление (смена статуса)
- `GET /api/v1/tasks/stats` — статистика (всего, по статусам, % выполнения за месяц)
- `GET /api/v1/tasks/urgent` — топ-5 срочных (для дашборда)

Фоновая задача (Celery):
- Каждый день проверять задачи: если `due_date < today` и `status != completed` → пометить `overdue`

**Frontend:**

- `TasksList.tsx`: заменить моки на реальные данные
- `Dashboard.tsx`: блок «Срочные задачи» — `useQuery('tasks/urgent')`
- `Dashboard.tsx`: блок «Выполнение задач» — `useQuery('tasks/stats')`

### Задача 2.4 — Дашборд партнёра

**Backend:**

- `GET /api/v1/dashboard` — агрегированные данные. **Лимиты (не конфигурируются):** `urgent_tasks` — макс. 5, `recent_clients` — макс. 5.
```json
{
  "debt_banner": {
    "total_debt": 18_500_000,
    "overdue": 4_500_000,
    "days_until_payment": 3,
    "has_debt": true
  },
  "stats": {
    "total_clients": 24,
    "new_this_week": 3,
    "before_court": 8,
    "in_court": 16,
    "completed": 45,
    "completed_this_month": 2
  },
  "urgent_tasks": [...],
  "task_completion": {
    "percent": 90,
    "weeks": [
      { "week": 1, "completed": 8, "total": 10 },
      ...
    ]
  },
  "recent_clients": [...]
}
```

**Frontend:**

- `Dashboard.tsx`: один запрос `useQuery('dashboard')`, распределение данных по виджетам

### Задача 2.5 — Дашборд админа

**Backend:**

- `GET /api/v1/admin/dashboard?period=7d` (или `start_date` + `end_date`). **Лимиты:** `top_partners` — макс. 10, `recent_transactions` — макс. 20.
```json
{
  "main_stats": {
    "partners_count": 49,
    "new_debtors": 12,
    "total_charged": 48_000_000
  },
  "movement_stats": {
    "in_progress": 156,
    "completed": 8,
    "rejected": 2
  },
  "total_balance": 607_387_676,
  "top_partners": [...],
  "recent_transactions": [...]
}
```

**Frontend:**

- `AdminDashboard.tsx`: подключить к реальному API с учётом выбранного периода

---

## Фаза 3 — Финансы и Документы

**Цель:** Судебные расходы, история платежей, генерация документов.

### Задача 3.1 — Судебные расходы (CourtFees)

**Backend:**

Модель `CourtFee` (наследует `Base`, `TimestampMixin`, `SoftDeleteMixin`; в выборках фильтровать по `deleted_at.is_(None)`):
```python
class CourtFee(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "court_fees"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"), index=True)
    amount: Mapped[int]  # сумма в копейках
    status: Mapped[str] = mapped_column(String(20), index=True)  # unpaid | paid | overdue
    due_date: Mapped[date] = mapped_column(index=True)  # court_procedure_date + payment_term_days
    paid_at: Mapped[Optional[datetime]]
```

Модель `Transaction` (наследует `Base`, `TimestampMixin`):
```python
class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"))
    court_fee_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("court_fees.id"))
    amount: Mapped[int]  # в копейках
    status: Mapped[str] = mapped_column(String(20))  # pending | completed | failed
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    external_id: Mapped[Optional[str]]  # ID в платёжной системе
```

Сервис `FinanceService`:
- При создании клиента типа `in_court` с `court_procedure_date` → авто-создание `CourtFee`
- При заполнении `court_procedure_date` админом → авто-создание `CourtFee` со сроком `court_procedure_date + partner.payment_term_days`
- Ежедневная Celery-задача: пометить `CourtFee` как `overdue` если `due_date < today` и `status = unpaid`

Эндпоинты:
- `GET /api/v1/finance/court-fees` — список расходов для партнёра
- `GET /api/v1/finance/court-fees/summary` — сводка (стоимость за клиента, задолженность, оплачено за месяц, кол-во к оплате)
- `GET /api/v1/finance/debt-banner` — данные для баннера на дашборде
- `POST /api/v1/finance/pay` — инициировать оплату (→ интеграция с платёжным шлюзом, пока заглушка)
- `GET /api/v1/finance/history` — история транзакций

**Frontend:**

- `CourtFees.tsx`: подключить к реальным данным
- Модалка оплаты: пока mock, в будущем — интеграция с ЮKassa / Тинькофф

### Задача 3.2 — Генерация документов

**Backend:**

Модель `Document` (наследует `Base`, `TimestampMixin`, `SoftDeleteMixin`; в выборках фильтровать по `deleted_at.is_(None)`):
```python
class Document(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"))
    type: Mapped[str] = mapped_column(String(50))  # bankruptcy_application, creditor_list, property_inventory, etc.
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))  # pending | ready | error
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    generated_at: Mapped[Optional[datetime]]
```

Типы документов (из спеки):
1. Заявление о признании гражданина банкротом
2. Список кредиторов
3. Опись имущества
4. Ходатайство о введении процедуры
5. Квитанция об оплате госпошлины

Сервис `DocumentService`:
- `generate_document(client_id, doc_type)` — на основе шаблона DOCX и данных клиента
- Использует `python-docx` для DOCX и `WeasyPrint` для PDF
- Шаблоны хранятся в `app/templates/` (физически каталог `backend/app/templates/`). Путь в коде — относительно корня приложения или через `Path(__file__).parent.parent / "templates"`.
- Результат сохраняется в S3/MinIO

Эндпоинты:
- `GET /api/v1/documents?client_id=...` — список документов клиента
- `POST /api/v1/documents/generate` → `{ client_id, doc_type }`
- `GET /api/v1/documents/{id}/download` — pre-signed URL
- `GET /api/v1/documents/{id}/preview` — PDF-версия для просмотра
- `POST /api/v1/documents/download-all?client_id=...` — ZIP-архив

**Frontend:**

- `DocumentGeneration.tsx`: подключить к API, отображать реальные статусы, кнопки скачивания

---

## Фаза 4 — Чат и Уведомления

**Цель:** Real-time чат (включая нейропомощника) и система уведомлений.

### Задача 4.1 — Чат

**Backend:**

Модели (наследуют `Base`, `TimestampMixin`):
```python
class ChatRoom(Base, TimestampMixin):
    __tablename__ = "chat_rooms"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"))
    type: Mapped[str] = mapped_column(String(20))  # arbitration_manager | assistant | ai_assistant

class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_rooms.id"), index=True)
    sender_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)  # NULL для bot
    sender_type: Mapped[str] = mapped_column(String(20))  # user | admin | bot
    text: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(default=False)
```

REST эндпоинты:
- `GET /api/v1/chat/rooms` — список чат-комнат партнёра
- `GET /api/v1/chat/rooms/{id}/messages?limit=50&before=cursor` — история сообщений (cursor pagination)
- `POST /api/v1/chat/rooms/{id}/messages` — отправка (fallback без WebSocket)

WebSocket:
- `WS /api/v1/ws/chat?token=...`
- При подключении: авторизация через JWT query param
- Форматы сообщений: `{ type: "message", room_id, text }` / `{ type: "typing", room_id }`
- Сервер рассылает всем участникам комнаты

Нейропомощник:
- При отправке в комнату типа `ai_assistant` → запрос к LLM API (OpenAI / другой)
- Контекст: последние N сообщений + информация о клиентах партнёра
- Ответ бота сохраняется как `ChatMessage` с `sender_type = "bot"`

**Frontend:**

- `Chat.tsx`: 
  - Подключить WebSocket при маунте, отключить при unmount
  - **Reconnection:** При обрыве соединения — exponential backoff (1s → 2s → 4s → max 30s). Показать пользователю индикатор «Переподключение...». При восстановлении — подгрузить пропущенные сообщения через REST (по `last_message_id`)
  - Загрузка истории через REST при переключении комнат
  - Scroll-to-bottom при новых сообщениях
  - Индикатор "печатает..."

### Задача 4.2 — Уведомления

**Backend:**

Модель `Notification` (наследует `Base`, `TimestampMixin`):
```python
class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(default=False, index=True)
    link: Mapped[Optional[str]] = mapped_column(String(255))
```

Триггеры уведомлений:
- Новый клиент у партнёра → уведомление админу
- Смена статуса клиента → уведомление партнёру
- Новая задача → уведомление исполнителю
- Просрочка оплаты → уведомление партнёру
- Новый партнёр (регистрация) → уведомление админу

Эндпоинты:
- `GET /api/v1/notifications?is_read=false` — список
- `PUT /api/v1/notifications/{id}/read` — пометить прочитанным
- `PUT /api/v1/notifications/read-all` — пометить все

**Frontend:**

- Компонент `NotificationBell` в хедере Layout:
  - Badge с числом непрочитанных
  - Dropdown со списком уведомлений
  - Polling каждые 30 секунд (или через WebSocket)

---

## Фаза 5 — Обучение, Настройки, Полировка

### Задача 5.1 — Обучение (Training)

**Backend:**

Модели (все наследуют `Base` и `TimestampMixin`; `created_at`/`updated_at` из миксина):
```python
class TrainingVideo(Base, TimestampMixin):
    __tablename__ = "training_videos"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    duration: Mapped[Optional[int]]  # секунды
    video_url: Mapped[str] = mapped_column(String(500))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500))
    order: Mapped[int] = mapped_column(default=0)

class FAQ(Base, TimestampMixin):
    __tablename__ = "faqs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(default=0)

class Instruction(Base, TimestampMixin):
    __tablename__ = "instructions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    steps: Mapped[dict] = mapped_column(JSON)  # список шагов
    order: Mapped[int] = mapped_column(default=0)

class ImportantNote(Base, TimestampMixin):
    __tablename__ = "important_notes"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[Optional[str]] = mapped_column(String(50))
    order: Mapped[int] = mapped_column(default=0)
```

Эндпоинты:
- `GET /api/v1/training/videos`
- `GET /api/v1/training/faq`
- `GET /api/v1/training/instructions`
- `GET /api/v1/training/important`

Админские эндпоинты для CRUD контента — в будущем.

**Frontend:**

- `Training.tsx`: подключить к API по всем вкладкам

### Задача 5.2 — Настройки системы (AdminSettings)

**Backend:**

Модель `SystemSetting` (key-value; наследует `Base`, без SoftDelete):
```python
class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
```

Модель `NotificationPreference` (наследует `Base`, `TimestampMixin`):
```python
class NotificationPreference(Base, TimestampMixin):
    __tablename__ = "notification_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    email_notifications: Mapped[bool] = mapped_column(default=True)
    new_partner_notifications: Mapped[bool] = mapped_column(default=True)
    critical_events: Mapped[bool] = mapped_column(default=True)
```

Эндпоинты:
- `GET /api/v1/admin/settings`
- `PUT /api/v1/admin/settings`
- `PUT /api/v1/admin/settings/notifications`
- `POST /api/v1/admin/settings/change-password`
- `GET /api/v1/admin/settings/login-history`
- `POST /api/v1/admin/settings/backup` (триггер бэкапа)

**Frontend:**

- `AdminSettings.tsx`: подключить к API

### Задача 5.3 — Полировка UI

- Skeleton-лоадеры при загрузке данных (используя `components/ui/skeleton.tsx`)
- Error boundaries + fallback UI
- Toast-уведомления через `sonner` (уже в зависимостях)
- Пагинация для длинных списков
- Responsive: мобильная адаптация (hamburger-меню для sidebar)
- Breadcrumbs на вложенных страницах
- Подтверждения опасных действий (delete) через `AlertDialog`

### Задача 5.4 — Удаление ненужных страниц/маршрутов

Из спецификации следует, что некоторые маршруты финансов лишние:
- `/dashboard/finance/payments` (PaymentStatuses) — **удалить** (нет в спеке)
- `/dashboard/finance/invoices` (CompletedActs) — **удалить** (нет в спеке)
- `/dashboard/finance/history` (FinanceHistory) — **оставить** как историю транзакций

Также привести auth-роуты к спецификации:
- `AdminLogin.tsx` — **удалить из production route map**
- `/` — **только redirect**
- `/login` — **единая точка входа**

Маршрут `/register` — оставить, но подключить к API.

---

## Инструкции для ИИ-агента

> Этот раздел — инструкция для ИИ Opus 4.6 по выполнению плана.

### Порядок работы

Строго последовательно, фаза за фазой. Внутри фазы — задачи можно параллелить, если нет зависимостей.

```
Фаза 0 (инфра)
  └─> Фаза 1 (auth + CRUD) 
        └─> Фаза 2 (бизнес-логика)
              └─> Фаза 3 (финансы + документы)
                    └─> Фаза 4 (чат + уведомления)
                          └─> Фаза 5 (обучение + полировка)
```

### Правила для каждой задачи

1. **Decision-first:** Если в задаче есть неоднозначность, сначала открой `docs/DECISIONS.md`. Если решения нет — зафиксируй вопрос, не придумывай финальное поведение самостоятельно.
2. **Contract-first:** Перед реализацией крупного блока зафиксируй request/response DTO, коды ошибок и пустые состояния.
3. **Backend-first:** Сначала создай модель, миграцию, сервис, API-эндпоинт. Проверь через тест или ручной запрос.
4. **Frontend-second:** Создай API-клиент (`api/*.ts`), хук (`hooks/use*.ts`), подключи к странице. Замени хардкод на реальные данные.
5. **Типы синхронизированы:** Pydantic-схемы бэка и TypeScript-интерфейсы фронта должны соответствовать друг другу. При изменении модели — обнови оба.
6. **Пустые состояния:** Всегда реализуй обработку пустых данных согласно спецификации (`PARTNER_CABINET_SPEC.md`).
7. **RBAC:** Каждый эндпоинт должен проверять роль. Партнёр видит только свои данные, админ — все.
8. **Screen-by-screen ready:** задача завершена только если экран соответствует спеке не только по данным, но и по фильтрам, CTA, empty state и маршрутам.

### Структура файлов — куда что класть

| Что | Куда |
|-----|------|
| SQLAlchemy модель | `backend/app/models/<entity>.py` |
| Pydantic схема | `backend/app/schemas/<entity>.py` |
| API роут | `backend/app/api/<entity>.py` |
| Бизнес-логика | `backend/app/services/<entity>_service.py` |
| Миграция | `poetry run alembic revision --autogenerate -m "..."` |
| API-клиент (фронт) | `frontend/src/app/api/<entity>.ts` |
| React Query хук | `frontend/src/app/hooks/use<Entity>.ts` |
| Zustand store | `frontend/src/app/store/<name>Store.ts` (только auth, ui — НЕ серверные данные) |

### Ключевые соглашения

- **Poetry:** Все Python-команды выполняются через `poetry run`. Новые зависимости — через `poetry add <pkg>` (или `poetry add --group dev <pkg>`). Никогда не использовать `pip install`. Файл `poetry.lock` коммитится в репозиторий.
- **API версионирование:** `/api/v1/...`
- **Naming:** snake_case в Python, camelCase в TypeScript. API возвращает snake_case — фронт трансформирует через axios interceptor или в хуках.
- **Аутентификация:** `Authorization: Bearer <token>` в каждом запросе.
- **Пароли:** минимум 8 символов (валидация на бэкенде и в zod-схемах фронта).
- **Ошибки:** Backend возвращает `{ detail: "...", code: "ERROR_CODE" }` с корректным HTTP-кодом. `code` — машиночитаемый идентификатор ошибки (см. ниже). Frontend обрабатывает через axios interceptor: по `code` можно показать специфичное сообщение, по умолчанию — `detail` в toast (`sonner`).
- **Пагинация:** `GET /api/v1/clients?page=1&page_size=20` → `{ items: [...], total: N, page: 1, pages: 5 }`. Параметр `page_size` по умолчанию 20, максимум 100.
- **Фильтры:** query-параметрами: `?search=иванов&type=before_court&status=new`
- **Даты:** ISO 8601 (`2026-02-15T10:30:00Z`) в API, форматирование на фронте через `date-fns`.
- **Деньги:** Все суммы хранятся и передаются в API **в копейках** (`int`). Конвертация в рубли — только на фронтенде при отображении. Пример: 15 000 ₽ = `1_500_000` в БД и API. Утилита на фронте: `formatMoney(kopecks: number): string` → `"15 000 ₽"`.
- **Формы:** Все формы на фронтенде через `react-hook-form` + `zod` для валидации. Не использовать сырые `useState` + `handleChange` для форм. `zod`-схемы должны отражать Pydantic-схемы бэкенда.
- **Логирование:** `structlog` на бэкенде. Каждый запрос логируется с `request_id`. Уровни: DEBUG (dev), INFO (prod). Не использовать `print()`.
- **Коды ошибок (примеры):**
  | HTTP | code | Когда |
  |------|------|-------|
  | 400 | `INVALID_STATUS_TRANSITION` | Недопустимый переход статуса клиента |
  | 400 | `VALIDATION_ERROR` | Ошибка валидации входных данных |
  | 401 | `TOKEN_EXPIRED` | access_token истёк |
  | 401 | `INVALID_CREDENTIALS` | Неверный email/пароль |
  | 403 | `FORBIDDEN` | Нет прав на операцию |
  | 404 | `NOT_FOUND` | Ресурс не найден |
  | 409 | `DUPLICATE_EMAIL` | Email уже зарегистрирован |
  | 413 | `FILE_TOO_LARGE` | Файл превышает лимит |
  | 415 | `UNSUPPORTED_FILE_TYPE` | Недопустимый тип файла |
  | 429 | `RATE_LIMITED` | Превышен лимит запросов |

  Формат ответа:
  ```json
  { "detail": "Человекочитаемое сообщение", "code": "INVALID_STATUS_TRANSITION" }
  ```
  Определять в `core/exceptions.py` как кастомные `HTTPException` с полем `code`.
- **Персональные данные (152-ФЗ):** Поля `passport_series`, `passport_number`, `passport_issued_by`, `snils`, `inn` содержат чувствительные ПДн. На первом этапе — хранить как есть, но **пометить техдолгом** шифрование этих полей (AES-256 на уровне приложения). Доступ к ПДн — только через сервисный слой, никогда напрямую из API-роутов.

### Стратегия тестирования

**Backend:**
- Структура `tests/` зеркалит `app/`:
  ```
  tests/
  ├── conftest.py                # Фикстуры: test DB, test client, auth tokens
  ├── api/
  │   ├── test_auth.py           # Login, refresh, logout, register
  │   ├── test_clients.py        # CRUD клиентов + RBAC
  │   ├── test_tasks.py
  │   └── test_finance.py
  └── services/
      ├── test_client_service.py  # Статус-машина, прогресс
      └── test_finance_service.py # Расчёт задолженностей
  ```
- **Минимум для каждого эндпоинта:** happy-path тест + тест на 401/403
- **Минимум для каждого сервиса:** happy-path + edge case (пустые данные, невалидный переход статуса)
- Использовать `httpx.AsyncClient` + `pytest-asyncio`
- Тестовая БД: отдельная PostgreSQL (или SQLite в memory для быстрых тестов)
- Каркас `conftest.py`:
```python
import asyncio
from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import get_db
from app.models import Base
from app.core.security import create_access_token

TEST_DATABASE_URL = "postgresql+asyncpg://app:secret@localhost:5432/partner_cabinet_test"

engine_test = create_async_engine(TEST_DATABASE_URL)
async_session_test = async_sessionmaker(engine_test, expire_on_commit=False)

async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_test() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def admin_token(setup_db) -> str:
    """Создаёт admin-пользователя и возвращает его access_token."""
    # INSERT admin в тестовую БД, вернуть create_access_token({"sub": str(admin.id)})
    ...

@pytest.fixture
async def partner_token(setup_db) -> str:
    """Создаёт partner-пользователя и возвращает его access_token."""
    ...
```
Каждый тест использует `client` и при необходимости `admin_token`/`partner_token` для авторизованных запросов: `client.get("/api/v1/...", headers={"Authorization": f"Bearer {admin_token}"})`.

**Frontend:**
- На первых фазах тесты фронта — опционально (приоритет на бэкенд)
- В дальнейшем: Vitest + React Testing Library для критичных компонентов
- Для сквозных сценариев добавить **Playwright smoke e2e**:
  - login партнёра
  - login админа
  - создание клиента
  - смена статуса клиента
  - просмотр судебных расходов
  - генерация и скачивание документа

**Правило:** каждая задача считается завершённой, только когда:
1. Код написан
2. Хотя бы happy-path тест проходит
3. Линтер не ругается (`poetry run ruff check .`)

### Что НЕ делать

- Не трогать `components/ui/` — это сгенерированные shadcn-компоненты, они работают
- Не менять структуру маршрутов без необходимости — текущая навигация соответствует спеке
- Не реализовывать платёжный шлюз на первых фазах — сначала заглушки
- Не создавать отдельный микросервис для чата — всё в одном FastAPI-приложении
- Не удалять скриншоты и спецификацию — это живая документация

### Файлы-источники для контекста

При работе над каждой задачей **обязательно** перечитай:

1. **`docs/PARTNER_CABINET_SPEC.md`** — соответствующий раздел (номера совпадают с разделами спеки)
2. **Скриншоты** из `docs/screenshots/` и `docs/screenadmin/` — визуальный референс
3. **Существующий компонент** из `frontend/src/app/pages/` — текущая реализация UI

### Чеклист готовности каждой фазы

- [ ] Все модели созданы и мигрированы
- [ ] Все эндпоинты работают (проверены через curl/httpie)
- [ ] Фронтенд-страницы подключены к API
- [ ] Хардкод-данные удалены из компонентов
- [ ] Пустые состояния отображаются корректно
- [ ] RBAC работает (партнёр не видит чужие данные, админ видит все)
- [ ] Нет console.log/console.error в production-коде

---

## Оценка трудоёмкости

| Фаза | Описание | Примерный объём |
|------|----------|-----------------|
| 0 | Инфраструктура | 15-20 файлов |
| 1 | Auth + CRUD | 30-40 файлов |
| 2 | Бизнес-логика | 20-30 файлов |
| 3 | Финансы + Документы | 15-25 файлов |
| 4 | Чат + Уведомления | 10-15 файлов |
| 5 | Обучение + Полировка | 10-15 файлов |
| **Итого** | | **~100-145 файлов** |

---

*Этот план является живым документом. По мере реализации уточняй детали и обновляй чеклисты.*
