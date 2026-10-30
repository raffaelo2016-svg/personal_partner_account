"""Unit-тесты: категоризация клиентов, BEFORE_COURT/IN_COURT статусы."""

import pytest

from app.models.enums import ClientStatus
from app.services.client_service import BEFORE_COURT_STATUSES, COMPLETED_STATUSES, IN_COURT_STATUSES


class TestStatusCategories:
    """Категории: before_court, in_court, completed."""

    def test_before_court_statuses(self):
        expected = {"documents_collection", "documents_formation", "sent_to_court", "documents_decision"}
        assert set(BEFORE_COURT_STATUSES) == expected

    def test_in_court_statuses(self):
        expected = {"waiting_hearing", "restructuring", "auction"}
        assert set(IN_COURT_STATUSES) == expected

    def test_no_overlap(self):
        """before_court и in_court не пересекаются."""
        assert set(BEFORE_COURT_STATUSES).isdisjoint(set(IN_COURT_STATUSES))

    def test_realization_and_completed_are_terminal(self):
        """realization и completed не входят ни в before_court, ни в in_court."""
        for status in ("realization", "completed"):
            assert status not in BEFORE_COURT_STATUSES
            assert status not in IN_COURT_STATUSES
            assert status in COMPLETED_STATUSES

    def test_all_statuses_categorized(self):
        """Каждый статус принадлежит ровно одной категории."""
        all_categorized = set(BEFORE_COURT_STATUSES) | set(IN_COURT_STATUSES) | set(COMPLETED_STATUSES)
        all_enum = {s.value for s in ClientStatus}
        assert all_categorized == all_enum

    @pytest.mark.parametrize(
        "status,category",
        [
            ("documents_collection", "before_court"),
            ("documents_formation", "before_court"),
            ("sent_to_court", "before_court"),
            ("documents_decision", "before_court"),
            ("waiting_hearing", "in_court"),
            ("restructuring", "in_court"),
            ("auction", "in_court"),
            ("realization", "completed"),
            ("completed", "completed"),
        ],
    )
    def test_each_status_category(self, status, category):
        if category == "before_court":
            assert status in BEFORE_COURT_STATUSES
        elif category == "in_court":
            assert status in IN_COURT_STATUSES
        else:
            assert status in COMPLETED_STATUSES


class TestProgressPercent:
    """Расчёт процента прогресса — чистая логика."""

    TOTAL_STAGES = 8

    @staticmethod
    def calc_percent(completed: int, total: int = 8) -> int:
        return round((completed / total) * 100) if total > 0 else 0

    def test_zero_completed(self):
        assert self.calc_percent(0) == 0

    def test_all_completed(self):
        assert self.calc_percent(8) == 100

    def test_half_completed(self):
        assert self.calc_percent(4) == 50

    def test_one_completed(self):
        assert self.calc_percent(1) == 12  # round(12.5) = 12 (banker's rounding)

    def test_seven_completed(self):
        assert self.calc_percent(7) == 88  # round(87.5)

    def test_monotonic(self):
        values = [self.calc_percent(i) for i in range(9)]
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1]
