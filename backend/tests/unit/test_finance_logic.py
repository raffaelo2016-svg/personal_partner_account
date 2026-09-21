"""Unit-тесты: Finance — расчёты, форматирование, логика оплаты."""

from datetime import date, timedelta

from app.services.partner_service import add_calendar_month


def test_add_calendar_month_keeps_day_when_available():
    assert add_calendar_month(date(2026, 9, 7)) == date(2026, 10, 7)


def test_add_calendar_month_clamps_to_month_end():
    assert add_calendar_month(date(2026, 1, 31)) == date(2026, 2, 28)


class TestDueDateCalculation:
    """Расчёт due_date для court_fee."""

    @staticmethod
    def calc_due_date(court_procedure_date: date, payment_term_days: int) -> date:
        return court_procedure_date + timedelta(days=payment_term_days)

    def test_10_days(self):
        assert self.calc_due_date(date(2026, 6, 1), 10) == date(2026, 6, 11)

    def test_30_days(self):
        assert self.calc_due_date(date(2026, 1, 1), 30) == date(2026, 1, 31)

    def test_0_days(self):
        assert self.calc_due_date(date(2026, 6, 1), 0) == date(2026, 6, 1)

    def test_cross_month(self):
        assert self.calc_due_date(date(2026, 1, 25), 10) == date(2026, 2, 4)


class TestOverdueDetection:
    """Определение просроченных платежей."""

    @staticmethod
    def is_overdue(due_date: date, status: str) -> bool:
        if status == "paid":
            return False
        return due_date < date.today()

    def test_unpaid_past_due(self):
        assert self.is_overdue(date(2020, 1, 1), "unpaid") is True

    def test_unpaid_future(self):
        assert self.is_overdue(date(2099, 1, 1), "unpaid") is False

    def test_paid_past_due(self):
        assert self.is_overdue(date(2020, 1, 1), "paid") is False


class TestDebtSummary:
    """Суммирование долгов."""

    @staticmethod
    def calc_summary(fees: list[dict]) -> dict:
        total = sum(f["amount"] for f in fees if f["status"] != "paid")
        overdue = sum(f["amount"] for f in fees if f["status"] == "overdue")
        current = total - overdue
        return {"total_debt": total, "overdue_debt": overdue, "current_debt": current}

    def test_no_fees(self):
        assert self.calc_summary([]) == {"total_debt": 0, "overdue_debt": 0, "current_debt": 0}

    def test_one_unpaid(self):
        r = self.calc_summary([{"amount": 1500, "status": "unpaid"}])
        assert r["total_debt"] == 1500
        assert r["current_debt"] == 1500

    def test_one_overdue(self):
        r = self.calc_summary([{"amount": 1500, "status": "overdue"}])
        assert r["overdue_debt"] == 1500
        assert r["current_debt"] == 0

    def test_paid_excluded(self):
        r = self.calc_summary([{"amount": 1500, "status": "paid"}, {"amount": 2000, "status": "unpaid"}])
        assert r["total_debt"] == 2000

    def test_mixed(self):
        fees = [
            {"amount": 1000, "status": "unpaid"},
            {"amount": 2000, "status": "overdue"},
            {"amount": 3000, "status": "paid"},
        ]
        r = self.calc_summary(fees)
        assert r["total_debt"] == 3000
        assert r["overdue_debt"] == 2000
        assert r["current_debt"] == 1000
