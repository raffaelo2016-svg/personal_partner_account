"""Regression: невалидный пароль при регистрации должен возвращать 422, не 500.

Фон: в Pydantic v2 ValueError из field_validator попадает в err['ctx']['error']
как Python-исключение. Если validation_exception_handler отдавал бы этот dict
как JSON напрямую, получали бы TypeError → 500. Тест проверяет, что:

1. ответ именно 422;
2. структура content = {"code": "VALIDATION_ERROR", "detail": [{"type","loc","msg"}]};
3. сообщение валидатора доходит до клиента без префикса Pydantic "Value error, ".
"""

from httpx import AsyncClient

BASE_PAYLOAD = {
    "email": "validation-case@test.com",
    "company_name": "ООО Тест",
    "director_name": "Иванов Иван",
    "inn": "7701234567",
    "phone": "+79991234567",
    "region": "Белгородская область",
}


async def _post(client: AsyncClient, password: str):
    return await client.post("/api/v1/auth/register", json={**BASE_PAYLOAD, "password": password})


class TestRegisterPasswordValidation:
    async def test_digits_only_returns_422_with_letter_message(self, client: AsyncClient, setup_db):
        resp = await _post(client, "1234567890")
        assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["code"] == "VALIDATION_ERROR"
        assert isinstance(body["detail"], list) and body["detail"], "detail должен быть непустым списком"
        pwd_err = next((e for e in body["detail"] if "password" in e.get("loc", [])), None)
        assert pwd_err, f"Нет ошибки для поля password в {body['detail']}"
        assert set(pwd_err.keys()) >= {"type", "loc", "msg"}
        assert not pwd_err["msg"].startswith("Value error,"), "Префикс Pydantic должен быть срезан"
        assert "букв" in pwd_err["msg"].lower(), f"msg={pwd_err['msg']!r}"

    async def test_letters_only_returns_422_with_digit_message(self, client: AsyncClient, setup_db):
        resp = await _post(client, "abcdefgh")
        assert resp.status_code == 422
        body = resp.json()
        pwd_err = next((e for e in body["detail"] if "password" in e.get("loc", [])), None)
        assert pwd_err, body
        assert "цифр" in pwd_err["msg"].lower()

    async def test_too_short_returns_422(self, client: AsyncClient, setup_db):
        resp = await _post(client, "ab1")
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "VALIDATION_ERROR"
        # Короткий пароль может отлавливаться либо Field(min_length=8), либо нашим
        # _validate_password_strength — оба варианта валидны, ловим по полю.
        pwd_err = next((e for e in body["detail"] if "password" in e.get("loc", [])), None)
        assert pwd_err, body

    async def test_valid_password_succeeds(self, client: AsyncClient, setup_db):
        """Позитивный sanity-check: валидный пароль регистрируется как раньше."""
        resp = await _post(client, "Qwerty123")
        assert resp.status_code == 201, resp.text
