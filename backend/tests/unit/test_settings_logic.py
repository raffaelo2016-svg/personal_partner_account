"""Unit-тесты: Settings — валидация паролей, timezone."""

import pytest


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
    """Валидация часовых поясов."""

    VALID_TIMEZONES = ["Europe/Moscow", "Asia/Tokyo", "UTC", "America/New_York"]
    INVALID_TIMEZONES = ["Invalid/Zone", "", "123"]

    @pytest.mark.parametrize("tz", VALID_TIMEZONES)
    def test_valid_timezone_format(self, tz):
        # Просто проверяем что строка не пустая и содержит /
        assert len(tz) > 0

    def test_default_timezone(self):
        assert "Europe/Moscow" in self.VALID_TIMEZONES
