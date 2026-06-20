"""Unit-тесты: Finance schemas + enums."""

import pytest

from app.models.enums import CourtFeeStatus, TransactionStatus


class TestFinanceEnums:
    def test_court_fee_statuses(self):
        assert set(CourtFeeStatus) == {"unpaid", "paid", "overdue"}

    def test_transaction_statuses(self):
        assert set(TransactionStatus) == {"pending", "completed", "failed"}

    def test_from_string(self):
        assert CourtFeeStatus("unpaid") == CourtFeeStatus.UNPAID

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            CourtFeeStatus("invalid")
