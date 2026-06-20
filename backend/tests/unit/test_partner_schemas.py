"""Unit-тесты: Partner schemas + enums."""

import pytest

from app.models.enums import PartnerStatus


class TestPartnerEnums:
    def test_statuses(self):
        assert set(PartnerStatus) == {"pending", "active", "blocked"}

    def test_count(self):
        assert len(PartnerStatus) == 3

    def test_from_string(self):
        assert PartnerStatus("active") == PartnerStatus.ACTIVE

    def test_invalid(self):
        with pytest.raises(ValueError):
            PartnerStatus("invalid")

    @pytest.mark.parametrize("s", ["pending", "active", "blocked"])
    def test_lowercase(self, s):
        assert PartnerStatus(s).value == s
