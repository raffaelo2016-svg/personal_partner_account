"""Unit-тесты: Pydantic схемы клиентов — валидация полей, граничные значения."""

import pytest
from pydantic import ValidationError

from app.schemas.client import ClientCreate, ClientUpdate


class TestClientCreate:
    """Валидация ClientCreate."""

    def test_minimal_valid(self):
        c = ClientCreate(type="before_court", full_name="Тест")
        assert c.full_name == "Тест"
        assert c.type == "before_court"

    def test_full_valid(self):
        c = ClientCreate(
            type="in_court",
            full_name="Иванов Иван",
            phone="+79991234567",
            email="a@b.com",
            passport_series="1234",
            passport_number="567890",
            inn="770123456789",
            snils="12345678901234",
            region="Москва",
            case_number="А40-123/2026",
        )
        assert c.email == "a@b.com"

    # ── Required fields ──

    def test_missing_type(self):
        with pytest.raises(ValidationError):
            ClientCreate(full_name="X")  # type: ignore[call-arg]

    def test_missing_full_name(self):
        with pytest.raises(ValidationError):
            ClientCreate(type="before_court")  # type: ignore[call-arg]

    # ── Type enum ──

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            ClientCreate(type="invalid", full_name="X")

    @pytest.mark.parametrize("t", ["before_court", "in_court"])
    def test_valid_types(self, t):
        c = ClientCreate(type=t, full_name="X")
        assert c.type == t

    # ── full_name constraints ──

    def test_empty_full_name(self):
        with pytest.raises(ValidationError):
            ClientCreate(type="before_court", full_name="")

    def test_max_full_name(self):
        c = ClientCreate(type="before_court", full_name="А" * 255)
        assert len(c.full_name) == 255

    def test_over_max_full_name(self):
        with pytest.raises(ValidationError):
            ClientCreate(type="before_court", full_name="А" * 256)

    def test_single_char_name(self):
        c = ClientCreate(type="before_court", full_name="Я")
        assert c.full_name == "Я"

    def test_unicode_name(self):
        c = ClientCreate(type="before_court", full_name="José O'Brien-Müller")
        assert "José" in c.full_name

    # ── max_length fields ──

    @pytest.mark.parametrize(
        "field,max_len",
        [
            ("passport_series", 4),
            ("passport_number", 6),
            ("inn", 12),
            ("snils", 14),
            ("phone", 20),
            ("email", 255),
            ("region", 100),
            ("arbitrage_court", 255),
            ("case_number", 50),
        ],
    )
    def test_field_at_max_length(self, field, max_len):
        data = {"type": "before_court", "full_name": "X", field: "x" * max_len}
        c = ClientCreate(**data)
        assert len(getattr(c, field)) == max_len

    @pytest.mark.parametrize(
        "field,max_len",
        [
            ("passport_series", 4),
            ("passport_number", 6),
            ("inn", 12),
            ("snils", 14),
            ("phone", 20),
            ("region", 100),
            ("case_number", 50),
        ],
    )
    def test_field_over_max_length(self, field, max_len):
        data = {"type": "before_court", "full_name": "X", field: "x" * (max_len + 1)}
        with pytest.raises(ValidationError):
            ClientCreate(**data)

    # ── Optional fields default to None ──

    def test_optional_fields_none(self):
        c = ClientCreate(type="before_court", full_name="X")
        assert c.phone is None
        assert c.email is None
        assert c.inn is None
        assert c.date_of_birth is None
        assert c.passport_series is None
        assert c.region is None

    # ── Date fields ──

    def test_date_of_birth_valid(self):
        from datetime import date

        c = ClientCreate(type="before_court", full_name="X", date_of_birth="1990-01-15")
        assert c.date_of_birth == date(1990, 1, 15)

    def test_date_of_birth_invalid_format(self):
        with pytest.raises(ValidationError):
            ClientCreate(type="before_court", full_name="X", date_of_birth="not-a-date")


class TestClientUpdate:
    """Валидация ClientUpdate — все поля опциональны."""

    def test_empty_update(self):
        u = ClientUpdate()
        assert u.full_name is None
        assert u.type is None

    def test_partial_update(self):
        u = ClientUpdate(full_name="Новое")
        assert u.full_name == "Новое"
        assert u.type is None

    def test_update_type(self):
        u = ClientUpdate(type="in_court")
        assert u.type == "in_court"

    def test_update_invalid_type(self):
        with pytest.raises(ValidationError):
            ClientUpdate(type="invalid")

    def test_update_status(self):
        u = ClientUpdate(status="documents_formation")
        assert u.status == "documents_formation"

    def test_update_invalid_status(self):
        with pytest.raises(ValidationError):
            ClientUpdate(status="fake_status")

    def test_exclude_unset(self):
        u = ClientUpdate(full_name="X")
        dumped = u.model_dump(exclude_unset=True)
        assert dumped == {"full_name": "X"}
        assert "type" not in dumped
        assert "phone" not in dumped

    def test_court_procedure_date(self):
        from datetime import date

        u = ClientUpdate(court_procedure_date="2026-06-15")
        assert u.court_procedure_date == date(2026, 6, 15)

    @pytest.mark.parametrize(
        "field,max_len",
        [
            ("passport_series", 4),
            ("inn", 12),
            ("phone", 20),
            ("case_number", 50),
        ],
    )
    def test_update_over_max_length(self, field, max_len):
        with pytest.raises(ValidationError):
            ClientUpdate(**{field: "x" * (max_len + 1)})
