"""Unit-тесты: Notification schemas + service logic."""

from datetime import datetime

from app.schemas.notification import NotificationRead


class TestNotificationRead:
    def test_valid(self):
        n = NotificationRead(
            id="abc",
            user_id="u1",
            type="info",
            title="Тест",
            message="Msg",
            is_read=False,
            link=None,
            created_at=datetime.now(),
        )
        assert n.is_read is False

    def test_with_link(self):
        n = NotificationRead(
            id="abc",
            user_id="u1",
            type="payment",
            title="Оплата",
            message="Msg",
            is_read=True,
            link="/finance",
            created_at=datetime.now(),
        )
        assert n.link == "/finance"

    def test_types_are_strings(self):
        """Все типы уведомлений — строки, нет enum."""
        for t in ("new_client", "status_change", "payment", "new_task", "overdue", "chat", "system"):
            n = NotificationRead(
                id="x",
                user_id="u",
                type=t,
                title="T",
                message="M",
                is_read=False,
                link=None,
                created_at=datetime.now(),
            )
            assert n.type == t
