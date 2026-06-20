"""Unit-тесты: app.validation.ru_requisites — формат ИНН/КПП."""

from __future__ import annotations

import pytest

from app.validation.ru_requisites import (
    digits_only,
    kpp_format_ok,
    normalize_and_validate_partner_inn_kpp,
)


class TestDigitsOnly:
    def test_none(self):
        assert digits_only(None) == ""

    def test_empty(self):
        assert digits_only("") == ""

    def test_dashes_stripped(self):
        assert digits_only("123-456") == "123456"

    def test_spaces_stripped(self):
        assert digits_only(" 1234 5") == "12345"

    def test_phone_formatted(self):
        assert digits_only("+7 (999) 123-45-67") == "79991234567"

    def test_letters_removed(self):
        assert digits_only("абвAB12C3") == "123"

    def test_unicode_digits_kept(self):
        """Метод .isdigit() считает арабо-индийские цифры цифрами — документируем поведение."""
        assert digits_only("۱۲۳") == "۱۲۳"


class TestKppFormatOk:
    def test_valid(self):
        assert kpp_format_ok("770101001") is True

    def test_too_short(self):
        assert kpp_format_ok("77010100") is False

    def test_too_long(self):
        assert kpp_format_ok("7701010011") is False

    def test_contains_letter(self):
        assert kpp_format_ok("77010X001") is False

    def test_pp_zero_zero_invalid(self):
        """Позиции 5–6 должны быть 01–99, не 00."""
        assert kpp_format_ok("771000001") is False

    def test_pp_upper_bound(self):
        assert kpp_format_ok("771099001") is True

    def test_pp_lower_bound(self):
        assert kpp_format_ok("771001001") is True


class TestNormalizeIndividual:
    def test_empty_inn_allowed(self):
        assert normalize_and_validate_partner_inn_kpp("individual", "", None) == ("", None)

    def test_none_inn_allowed(self):
        # digits_only("") == "", то же поведение
        assert normalize_and_validate_partner_inn_kpp("individual", "", "") == ("", None)

    def test_10_digits_ok(self):
        assert normalize_and_validate_partner_inn_kpp("individual", "7701234567", None) == (
            "7701234567",
            None,
        )

    def test_12_digits_ok(self):
        assert normalize_and_validate_partner_inn_kpp("individual", "770123456789", None) == (
            "770123456789",
            None,
        )

    def test_11_digits_rejected(self):
        with pytest.raises(ValueError, match="10 или 12 цифр"):
            normalize_and_validate_partner_inn_kpp("individual", "77012345678", None)

    def test_normalization_strips_separators(self):
        assert normalize_and_validate_partner_inn_kpp("individual", "77-01-23-45-67", None) == (
            "7701234567",
            None,
        )

    def test_kpp_ignored_for_individual(self):
        """Для individual kpp не нужен — возвращается None, даже если передали."""
        result = normalize_and_validate_partner_inn_kpp("individual", "7701234567", "770101001")
        assert result == ("7701234567", None)


class TestNormalizeLegal:
    def test_valid(self):
        assert normalize_and_validate_partner_inn_kpp("legal", "7701234567", "770101001") == (
            "7701234567",
            "770101001",
        )

    def test_inn_not_10(self):
        with pytest.raises(ValueError, match="ровно 10 цифр"):
            normalize_and_validate_partner_inn_kpp("legal", "770123456789", "770101001")

    def test_kpp_none_rejected(self):
        with pytest.raises(ValueError, match="КПП"):
            normalize_and_validate_partner_inn_kpp("legal", "7701234567", None)

    def test_kpp_malformed(self):
        with pytest.raises(ValueError, match="КПП"):
            normalize_and_validate_partner_inn_kpp("legal", "7701234567", "77010X001")

    def test_kpp_pp_zero(self):
        with pytest.raises(ValueError, match="КПП"):
            normalize_and_validate_partner_inn_kpp("legal", "7701234567", "771000001")


class TestNormalizeEntrepreneur:
    def test_valid(self):
        assert normalize_and_validate_partner_inn_kpp("entrepreneur", "770123456789", None) == (
            "770123456789",
            None,
        )

    def test_10_digits_rejected(self):
        with pytest.raises(ValueError, match="ровно 12 цифр"):
            normalize_and_validate_partner_inn_kpp("entrepreneur", "7701234567", None)

    def test_empty_rejected(self):
        with pytest.raises(ValueError, match="ровно 12 цифр"):
            normalize_and_validate_partner_inn_kpp("entrepreneur", "", None)


class TestNormalizeUnknownType:
    def test_raises(self):
        with pytest.raises(ValueError, match="Неизвестный тип"):
            normalize_and_validate_partner_inn_kpp("xxx", "7701234567", None)
