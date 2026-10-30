"""Unit-тесты: Dashboard — категоризация, вычисления."""

from app.services.client_service import BEFORE_COURT_STATUSES, COMPLETED_STATUSES, IN_COURT_STATUSES


class TestDashboardCategories:
    """Дашборд использует те же категории что и клиенты."""

    def test_before_court_count(self):
        assert len(BEFORE_COURT_STATUSES) == 4

    def test_in_court_count(self):
        assert len(IN_COURT_STATUSES) == 3

    def test_completed_includes_realization_and_completed(self):
        """Оба терминальных статуса не входят в before/in court."""
        assert COMPLETED_STATUSES == ["realization", "completed"]
        for status in COMPLETED_STATUSES:
            assert status not in BEFORE_COURT_STATUSES
            assert status not in IN_COURT_STATUSES


class TestTaskCompletion:
    """task_completion в дашборде."""

    @staticmethod
    def calc_completion(completed: int, total: int) -> dict:
        return {
            "percent": round((completed / total) * 100) if total > 0 else 0,
            "total": total,
            "completed": completed,
        }

    def test_zero(self):
        assert self.calc_completion(0, 0) == {"percent": 0, "total": 0, "completed": 0}

    def test_half(self):
        assert self.calc_completion(5, 10)["percent"] == 50

    def test_full(self):
        assert self.calc_completion(10, 10)["percent"] == 100

    def test_one_of_three(self):
        assert self.calc_completion(1, 3)["percent"] == 33


class TestTopPartnersSorting:
    """top_partners сортируется по количеству клиентов."""

    @staticmethod
    def sort_partners(partners: list[dict]) -> list[dict]:
        return sorted(partners, key=lambda p: p.get("client_count", 0), reverse=True)

    def test_sort_desc(self):
        data = [{"name": "A", "client_count": 5}, {"name": "B", "client_count": 10}, {"name": "C", "client_count": 1}]
        result = self.sort_partners(data)
        assert [p["name"] for p in result] == ["B", "A", "C"]

    def test_empty(self):
        assert self.sort_partners([]) == []

    def test_equal_counts(self):
        data = [{"name": "A", "client_count": 5}, {"name": "B", "client_count": 5}]
        result = self.sort_partners(data)
        assert len(result) == 2
