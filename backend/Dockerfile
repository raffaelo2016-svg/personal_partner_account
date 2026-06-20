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
# CMD задаётся в docker-compose.yml / docker-compose.prod.yml —
# там для prod `uvicorn ... --workers 2 --proxy-headers`, для dev `--reload`.
