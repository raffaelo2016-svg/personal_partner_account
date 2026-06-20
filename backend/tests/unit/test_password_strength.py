"""Unit-тесты: _validate_password_strength из app.schemas.auth."""

from __future__ import annotations

import pytest

from app.schemas.auth import _validate_password_strength


class TestHappyPaths:
    def test_latin_with_digit(self):
        assert _validate_password_strength("Qwerty123") == "Qwerty123"

    def test_cyrillic_with_digit(self):
        assert _validate_password_strength("Пароль12") == "Пароль12"

    def test_mixed_cyrillic_latin_digit(self):
        assert _validate_password_strength("Парol123") == "Парol123"

    def test_very_long(self):
        long_pwd = "a" * 999 + "1"
        assert _validate_password_strength(long_pwd) == long_pwd


class TestFailingPaths:
    def test_too_short(self):
        with pytest.raises(ValueError, match="минимум 8"):
            _validate_password_strength("aaaaaaa")  # 7

    def test_too_short_boundary_7(self):
        with pytest.raises(ValueError, match="минимум 8"):
            _validate_password_strength("abc1234")

    def test_eight_chars_ok(self):
        assert _validate_password_strength("abcd1234") == "abcd1234"

    def test_digits_only(self):
        with pytest.raises(ValueError, match="букв"):
            _validate_password_strength("12345678")

    def test_letters_only(self):
        with pytest.raises(ValueError, match="цифр"):
            _validate_password_strength("abcdefgh")

    def test_cyrillic_only_no_digits(self):
        with pytest.raises(ValueError, match="цифр"):
            _validate_password_strength("Парольчик")

    def test_special_chars_only(self):
        """Нет ни букв, ни цифр — падает на проверке буквы (первая в порядке)."""
        with pytest.raises(ValueError, match="букв"):
            _validate_password_strength("!@#$%^&*()")

    def test_validator_check_order_letter_before_digit(self):
        """
        Если нет ни букв, ни цифр — валидатор бросает ошибку про букву,
        а не про цифру (порядок проверок). Закрепляем порядок, т.к. юзеру
        показывается первая ошибка.
        """
        with pytest.raises(ValueError) as exc:
            _validate_password_strength("########")
        assert "букв" in str(exc.value)
        assert "цифр" not in str(exc.value)
