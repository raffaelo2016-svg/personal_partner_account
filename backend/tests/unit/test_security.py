"""Unit-тесты: app.core.security — bcrypt + JWT без БД и Redis."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from app.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_roundtrip(self):
        h = hash_password("Qwerty123")
        assert verify_password("Qwerty123", h) is True

    def test_wrong_password(self):
        h = hash_password("Qwerty123")
        assert verify_password("Qwerty124", h) is False

    def test_unicode_password(self):
        h = hash_password("Пар0ль!Ёж")
        assert verify_password("Пар0ль!Ёж", h) is True
        assert verify_password("Пар0ль!ёж", h) is False

    def test_empty_plain_vs_hash_of_nonempty(self):
        h = hash_password("Qwerty123")
        assert verify_password("", h) is False

    def test_hash_is_not_deterministic(self):
        """Два вызова hash_password дают разные хэши (случайная соль)."""
        assert hash_password("same") != hash_password("same")

    def test_malformed_hash_raises(self):
        """Битый хэш — bcrypt бросает ValueError. Закрепляем, чтобы случайно не проглотить."""
        with pytest.raises(ValueError):
            verify_password("whatever", "not-a-bcrypt-hash")


class TestAccessToken:
    def test_payload_contains_required_fields(self):
        token = create_access_token({"sub": "user-1", "role": "partner"})
        payload = decode_access_token(token)
        assert payload["sub"] == "user-1"
        assert payload["role"] == "partner"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_decode_refresh_token_as_access_rejected(self):
        refresh = create_refresh_token({"sub": "u", "role": "partner"})
        with pytest.raises(HTTPException) as exc:
            decode_access_token(refresh)
        assert exc.value.status_code == 401
        assert exc.value.headers["code"] == "INVALID_CREDENTIALS"

    def test_expired_access_token(self):
        expired = jwt.encode(
            {
                "sub": "u",
                "role": "partner",
                "type": "access",
                "exp": datetime.now(UTC) - timedelta(minutes=1),
            },
            settings.SECRET_KEY,
            algorithm=ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            decode_access_token(expired)
        assert exc.value.status_code == 401
        assert exc.value.headers["code"] == "TOKEN_EXPIRED"

    def test_token_signed_with_wrong_key(self):
        bad = jwt.encode(
            {
                "sub": "u",
                "role": "partner",
                "type": "access",
                "exp": datetime.now(UTC) + timedelta(minutes=10),
            },
            "some-other-key",
            algorithm=ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            decode_access_token(bad)
        assert exc.value.headers["code"] == "INVALID_CREDENTIALS"

    def test_garbage_string(self):
        with pytest.raises(HTTPException) as exc:
            decode_access_token("not.a.jwt")
        assert exc.value.status_code == 401


class TestRefreshToken:
    def test_has_jti_and_type(self):
        token = create_refresh_token({"sub": "u", "role": "partner"})
        payload = decode_refresh_token(token)
        assert payload["type"] == "refresh"
        assert "jti" in payload and len(payload["jti"]) >= 32

    def test_jti_unique_between_calls(self):
        a = decode_refresh_token(create_refresh_token({"sub": "u", "role": "p"}))
        b = decode_refresh_token(create_refresh_token({"sub": "u", "role": "p"}))
        assert a["jti"] != b["jti"]

    def test_access_token_rejected_as_refresh(self):
        access = create_access_token({"sub": "u", "role": "partner"})
        with pytest.raises(HTTPException) as exc:
            decode_refresh_token(access)
        assert exc.value.status_code == 401
        assert exc.value.headers["code"] == "INVALID_CREDENTIALS"

    def test_expired_refresh_token(self):
        expired = jwt.encode(
            {
                "sub": "u",
                "role": "partner",
                "type": "refresh",
                "jti": "fake-jti",
                "exp": datetime.now(UTC) - timedelta(days=1),
            },
            settings.SECRET_KEY,
            algorithm=ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            decode_refresh_token(expired)
        assert exc.value.headers["code"] == "TOKEN_EXPIRED"
