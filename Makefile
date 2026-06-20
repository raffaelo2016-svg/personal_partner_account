.PHONY: install dev dev-frontend migrate migrate-create seed test \
       lint lint-fix lint-ruff lint-mypy lint-bandit lint-format \
       format openapi typecheck build-frontend

install:
	cd backend && poetry install

dev:
	cd backend && poetry run uvicorn app.main:app --reload --port 8000

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

# ── Linting (all-in-one) ──────────────────────────────────────────

lint: lint-format lint-ruff lint-mypy lint-bandit

lint-fix:
	cd backend && poetry run ruff format .
	cd backend && poetry run ruff check . --fix

# ── Individual linters ────────────────────────────────────────────

lint-format:
	cd backend && poetry run ruff format --check .

lint-ruff:
	cd backend && poetry run ruff check .

lint-mypy:
	cd backend && poetry run mypy app/

lint-bandit:
	cd backend && poetry run bandit -r app/ -c pyproject.toml

# ── Other ─────────────────────────────────────────────────────────

format:
	cd backend && poetry run ruff format .

openapi:
	cd backend && poetry run python -m app.scripts.export_openapi

typecheck:
	cd frontend && npx tsc --noEmit

build-frontend:
	cd frontend && npm run build
