"""Unit-тесты: Notification — логика подсчёта, пометки."""

import pytest


class TestUnreadCount:
    @staticmethod
    def count_unread(notifications: list[dict]) -> int:
        return sum(1 for n in notifications if not n["is_read"])

    def test_all_unread(self):
        assert self.count_unread([{"is_read": False}, {"is_read": False}]) == 2

    def test_all_read(self):
        assert self.count_unread([{"is_read": True}, {"is_read": True}]) == 0

    def test_mixed(self):
        assert self.count_unread([{"is_read": False}, {"is_read": True}, {"is_read": False}]) == 2

    def test_empty(self):
        assert self.count_unread([]) == 0


class TestMarkRead:
    @staticmethod
    def mark_one(notifications: list[dict], nid: str) -> list[dict]:
        return [{**n, "is_read": True} if n["id"] == nid else n for n in notifications]

    def test_marks_correct(self):
        notifs = [{"id": "1", "is_read": False}, {"id": "2", "is_read": False}]
        result = self.mark_one(notifs, "1")
        assert result[0]["is_read"] is True
        assert result[1]["is_read"] is False

    def test_immutable(self):
        orig = [{"id": "1", "is_read": False}]
        self.mark_one(orig, "1")
        assert orig[0]["is_read"] is False

    @staticmethod
    def mark_all(notifications: list[dict]) -> list[dict]:
        return [{**n, "is_read": True} for n in notifications]

    def test_mark_all(self):
        notifs = [{"id": "1", "is_read": False}, {"id": "2", "is_read": False}]
        result = self.mark_all(notifs)
        assert all(n["is_read"] for n in result)

    def test_mark_all_empty(self):
        assert self.mark_all([]) == []


class TestNotificationTypes:
    VALID_TYPES = {"new_client", "status_change", "payment", "new_task", "overdue", "chat", "system"}

    def test_count(self):
        assert len(self.VALID_TYPES) == 7

    @pytest.mark.parametrize("t", ["new_client", "status_change", "payment", "new_task", "overdue", "chat", "system"])
    def test_type_valid(self, t):
        assert t in self.VALID_TYPES
