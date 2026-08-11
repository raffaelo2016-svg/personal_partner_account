from httpx import AsyncClient
from sqlalchemy import select

REGISTER_DATA = {
    "email": "newpartner@test.com",
    "password": "securepass123",
    "company_name": "ООО Тест",
    "director_name": "Иванов Иван",
    "inn": "7701234567",
    "phone": "+79991234567",
}


class TestRegister:
    async def test_register_success(self, client: AsyncClient, setup_db):
        resp = await client.post("/api/v1/auth/register", json=REGISTER_DATA)
        assert resp.status_code == 201
        data = resp.json()
        assert data["message"] == "Registration successful. Awaiting admin approval."
        assert data["user"]["email"] == "newpartner@test.com"
        assert data["user"]["role"] == "partner"

    async def test_register_ignores_financial_terms_from_partner(self, client: AsyncClient, setup_db):
        from app.models.partner import Partner
        from app.models.user import User
        from tests.conftest import async_session_test

        resp = await client.post(
            "/api/v1/auth/register",
            json={
                **REGISTER_DATA,
                "email": "terms@test.com",
                "court_fee_per_client": 99,
                "payment_term_days": 99,
            },
        )
        assert resp.status_code == 201

        async with async_session_test() as session:
            row = await session.execute(
                select(Partner).join(User, Partner.user_id == User.id).where(User.email == "terms@test.com"),
            )
            partner = row.scalar_one()
            assert partner.court_fee_per_client == 1_500_000
            assert partner.payment_term_days == 10

    async def test_register_duplicate_email(self, client: AsyncClient, setup_db):
        await client.post("/api/v1/auth/register", json=REGISTER_DATA)
        resp = await client.post("/api/v1/auth/register", json=REGISTER_DATA)
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "DUPLICATE_EMAIL"

    async def test_register_short_password(self, client: AsyncClient, setup_db):
        data = {**REGISTER_DATA, "password": "short"}
        resp = await client.post("/api/v1/auth/register", json=data)
        assert resp.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient, setup_db):
        data = {**REGISTER_DATA, "email": "not-an-email"}
        resp = await client.post("/api/v1/auth/register", json=data)
        assert resp.status_code == 422

    async def test_registered_user_cannot_login_until_approved(self, client: AsyncClient, setup_db):
        """Registered partner has status=pending → cannot login (PARTNER_PENDING)."""
        await client.post("/api/v1/auth/register", json=REGISTER_DATA)

        from unittest.mock import AsyncMock, patch

        with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
            mock_redis.setex = AsyncMock()
            login_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": REGISTER_DATA["email"], "password": REGISTER_DATA["password"]},
            )
            assert login_resp.status_code == 403
            assert login_resp.json()["code"] == "PARTNER_PENDING"

    async def test_registration_notifies_only_subscribed_active_admins(
        self,
        client: AsyncClient,
        setup_db,
    ):
        from app.core.security import hash_password
        from app.models.notification import Notification
        from app.models.settings import NotificationPreference
        from app.models.user import User
        from tests.conftest import async_session_test

        async with async_session_test() as session:
            subscribed_admin = User(
                email="subscribed-admin@test.com",
                hashed_password=hash_password("password123"),
                role="admin",
                is_active=True,
            )
            unsubscribed_admin = User(
                email="unsubscribed-admin@test.com",
                hashed_password=hash_password("password123"),
                role="admin",
                is_active=True,
            )
            inactive_admin = User(
                email="inactive-admin@test.com",
                hashed_password=hash_password("password123"),
                role="admin",
                is_active=False,
            )
            session.add_all([subscribed_admin, unsubscribed_admin, inactive_admin])
            await session.flush()
            session.add(
                NotificationPreference(
                    user_id=unsubscribed_admin.id,
                    new_partner_notifications=False,
                )
            )
            await session.commit()

        resp = await client.post(
            "/api/v1/auth/register",
            json={**REGISTER_DATA, "email": "notified-partner@test.com"},
        )
        assert resp.status_code == 201

        async with async_session_test() as session:
            notifications = (await session.execute(select(Notification))).scalars().all()

        assert len(notifications) == 1
        notification = notifications[0]
        assert notification.user_id == subscribed_admin.id
        assert notification.type == "new_partner"
        assert notification.title == "Новый партнёр ожидает активации"
        assert notification.message == "ООО Тест зарегистрирован в кабинете"
        assert notification.link and notification.link.startswith("/admin/partners/")


class TestRegisterCaptcha:
    """Yandex SmartCaptcha: при заданном YANDEX_CAPTCHA_SECRET_KEY публичная регистрация требует токен."""

    async def test_missing_token_rejected(self, client: AsyncClient, setup_db, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "YANDEX_CAPTCHA_SECRET_KEY", "test-secret")
        resp = await client.post("/api/v1/auth/register", json=REGISTER_DATA)
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "CAPTCHA_REQUIRED"

    async def test_invalid_token_rejected(self, client: AsyncClient, setup_db, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "YANDEX_CAPTCHA_SECRET_KEY", "test-secret")

        async def fake_verify(token: str, ip):
            return False

        monkeypatch.setattr("app.services.captcha_service.verify_captcha", fake_verify)
        resp = await client.post(
            "/api/v1/auth/register",
            json={**REGISTER_DATA, "captcha_token": "bad"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "CAPTCHA_INVALID"

    async def test_valid_token_accepted(self, client: AsyncClient, setup_db, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "YANDEX_CAPTCHA_SECRET_KEY", "test-secret")

        async def fake_verify(token: str, ip):
            return True

        monkeypatch.setattr("app.services.captcha_service.verify_captcha", fake_verify)
        resp = await client.post(
            "/api/v1/auth/register",
            json={**REGISTER_DATA, "captcha_token": "good"},
        )
        assert resp.status_code == 201

    async def test_admin_bypass(self, client: AsyncClient, setup_db, monkeypatch):
        """Админ с Bearer-токеном может использовать endpoint без капчи для совместимости."""
        from unittest.mock import AsyncMock, patch

        from app.config import settings
        from app.core.security import hash_password
        from app.models.user import User
        from tests.conftest import async_session_test

        async with async_session_test() as session:
            admin = User(
                email="captcha_admin@test.com",
                hashed_password=hash_password("admin123"),
                role="admin",
                is_active=True,
            )
            session.add(admin)
            await session.commit()

        with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
            mock_redis.setex = AsyncMock()
            login_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "captcha_admin@test.com", "password": "admin123"},
            )
            admin_token = login_resp.json()["access_token"]

        monkeypatch.setattr(settings, "YANDEX_CAPTCHA_SECRET_KEY", "test-secret")

        resp = await client.post(
            "/api/v1/auth/register",
            json=REGISTER_DATA,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
