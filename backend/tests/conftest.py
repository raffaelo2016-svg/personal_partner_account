import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.rate_limit import limiter
from app.database import get_db
from app.main import app
from app.models import Base

limiter.enabled = False

# CI уже задаёт DATABASE_URL, указывающий на partner_cabinet_test. Локально в
# config.py дефолт — partner_cabinet. Наивный .replace("/partner_cabinet", …)
# на CI дал бы "/partner_cabinet_test_test" (InvalidCatalogNameError), поэтому
# сначала смотрим, не ведёт ли URL уже на тестовую БД.
if settings.DATABASE_URL.rstrip("/").endswith("_test"):
    TEST_DATABASE_URL = settings.DATABASE_URL
else:
    TEST_DATABASE_URL = settings.DATABASE_URL.replace("/partner_cabinet", "/partner_cabinet_test")

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
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
