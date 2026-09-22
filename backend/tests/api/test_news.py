from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.partner import Partner
from app.models.user import User
from tests.conftest import async_session_test


@pytest.fixture(autouse=True)
def mock_access_revocation():
    with patch("app.services.auth_service.is_access_jti_revoked", new_callable=AsyncMock, return_value=False):
        yield


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def setup_users(client: AsyncClient):
    async with async_session_test() as session:
        admin = User(email="news_admin@test.com", hashed_password=hash_password("password123"), role="admin")
        partner = User(email="news_partner@test.com", hashed_password=hash_password("password123"), role="partner")
        session.add_all([admin, partner])
        await session.flush()
        session.add(
            Partner(
                user_id=partner.id,
                company_name="News Co",
                director_name="Dir",
                inn="7701234567",
                phone="+71234567890",
                status="active",
            )
        )
        await session.commit()

    tokens = []
    with patch("app.services.auth_service.redis_client", new_callable=AsyncMock) as mock_redis:
        mock_redis.setex = AsyncMock()
        for email in ("news_admin@test.com", "news_partner@test.com"):
            response = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
            assert response.status_code == 200
            tokens.append(response.json()["access_token"])
    return tokens


async def test_news_publication_read_and_acknowledgement(client: AsyncClient, setup_db):
    admin_token, partner_token = await setup_users(client)
    input_data = {
        "title": "Тестовое объявление",
        "body": "Текст для партнёров",
        "category": "announcement",
        "important": True,
        "pinned": True,
        "requires_acknowledgement": True,
    }
    draft = await client.post("/api/v1/admin/news", json=input_data, headers=auth(admin_token))
    assert draft.status_code == 201
    post_id = draft.json()["id"]

    hidden = await client.get("/api/v1/news", headers=auth(partner_token))
    assert hidden.json()["total"] == 0
    forbidden = await client.post("/api/v1/admin/news", json=input_data, headers=auth(partner_token))
    assert forbidden.status_code == 403

    published = await client.post(f"/api/v1/admin/news/{post_id}/publish", headers=auth(admin_token))
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    listed = await client.get("/api/v1/news", headers=auth(partner_token))
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["read_at"] is None
    count = await client.get("/api/v1/news/unread-count", headers=auth(partner_token))
    assert count.json()["count"] == 1

    read = await client.put(f"/api/v1/news/{post_id}/read", headers=auth(partner_token))
    assert read.status_code == 200
    assert read.json()["read_at"] is not None
    count = await client.get("/api/v1/news/unread-count", headers=auth(partner_token))
    assert count.json()["count"] == 0
    acknowledged = await client.put(f"/api/v1/news/{post_id}/acknowledge", headers=auth(partner_token))
    assert acknowledged.status_code == 200
    assert acknowledged.json()["acknowledged_at"] is not None

    stats = await client.get(f"/api/v1/admin/news/{post_id}/stats", headers=auth(admin_token))
    assert stats.json() == {"total": 1, "read": 1, "acknowledged": 1}
    archived = await client.post(f"/api/v1/admin/news/{post_id}/archive", headers=auth(admin_token))
    assert archived.status_code == 200
    assert (await client.get(f"/api/v1/news/{post_id}", headers=auth(partner_token))).status_code == 404


async def test_news_cover_upload_replace_and_remove(client: AsyncClient, setup_db):
    admin_token, partner_token = await setup_users(client)
    draft = await client.post(
        "/api/v1/admin/news",
        json={"title": "Новость с обложкой", "body": "Текст новости"},
        headers=auth(admin_token),
    )
    assert draft.status_code == 201
    post_id = draft.json()["id"]
    image_url = f"/api/v1/admin/news/{post_id}/image"
    png = b"\x89PNG\r\n\x1a\n" + b"test-image"

    with (
        patch("app.api.news.upload_file_async", new_callable=AsyncMock) as upload,
        patch("app.api.news.delete_file_async", new_callable=AsyncMock) as delete,
        patch("app.api.news.get_presigned_url", return_value="https://assets.test/cover") as presign,
    ):
        upload.side_effect = ["uploads/first.png", "uploads/second.png"]

        forbidden = await client.post(
            image_url, files={"file": ("cover.png", png, "image/png")}, headers=auth(partner_token)
        )
        assert forbidden.status_code == 403
        wrong_type = await client.post(
            image_url, files={"file": ("cover.svg", b"<svg/>", "image/svg+xml")}, headers=auth(admin_token)
        )
        assert wrong_type.status_code == 415
        mismatched_mime = await client.post(
            image_url, files={"file": ("cover.png", png, "image/jpeg")}, headers=auth(admin_token)
        )
        assert mismatched_mime.status_code == 415
        invalid_content = await client.post(
            image_url, files={"file": ("cover.png", b"not-an-image", "image/png")}, headers=auth(admin_token)
        )
        assert invalid_content.status_code == 415
        too_large = await client.post(
            image_url,
            files={"file": ("cover.png", png + b"x" * (5 * 1024 * 1024), "image/png")},
            headers=auth(admin_token),
        )
        assert too_large.status_code == 413
        upload.assert_not_awaited()

        first = await client.post(image_url, files={"file": ("cover.png", png, "image/png")}, headers=auth(admin_token))
        assert first.status_code == 200
        assert first.json()["image_url"] == "https://assets.test/cover"
        presign.assert_called_with("uploads/first.png", expires_in=3600)

        published = await client.post(f"/api/v1/admin/news/{post_id}/publish", headers=auth(admin_token))
        assert published.status_code == 200
        visible = await client.get("/api/v1/news", headers=auth(partner_token))
        assert visible.json()["items"][0]["image_url"] == "https://assets.test/cover"

        second = await client.post(
            image_url, files={"file": ("cover.png", png, "image/png")}, headers=auth(admin_token)
        )
        assert second.status_code == 200
        delete.assert_awaited_with("uploads/first.png")

        removed = await client.delete(image_url, headers=auth(admin_token))
        assert removed.status_code == 200
        assert removed.json()["image_url"] is None
        delete.assert_awaited_with("uploads/second.png")
        assert (await client.get(f"/api/v1/news/{post_id}", headers=auth(partner_token))).json()["image_url"] is None
