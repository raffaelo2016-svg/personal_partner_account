"""Unit-тесты: Settings — валидация паролей, timezone."""

from app.core.time import MOSCOW_TIMEZONE


class TestPasswordValidation:
    """Логика смены пароля."""

    @staticmethod
    def validate_new_password(password: str) -> str | None:
        if len(password) < 8:
            return "Минимум 8 символов"
        return None

    def test_valid(self):
        assert self.validate_new_password("newpass123") is None

    def test_short(self):
        assert self.validate_new_password("short") is not None

    def test_empty(self):
        assert self.validate_new_password("") is not None

    def test_exactly_8(self):
        assert self.validate_new_password("12345678") is None

    def test_7_chars(self):
        assert self.validate_new_password("1234567") is not None


class TestTimezoneValidation:
    """Единый часовой пояс кабинета."""

    def test_timezone_is_moscow(self):
        assert MOSCOW_TIMEZONE == "Europe/Moscow"
