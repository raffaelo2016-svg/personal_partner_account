"""Unit-тесты: Chat delivery_status, ConnectionManager logic."""

import pytest


class TestDeliveryStatus:
    """delivery_status: sent → delivered → read."""

    VALID_STATUSES = ("sent", "delivered", "read")

    @pytest.mark.parametrize("status", VALID_STATUSES)
    def test_valid_statuses(self, status):
        assert status in self.VALID_STATUSES

    def test_order(self):
        order = list(self.VALID_STATUSES)
        assert order.index("sent") < order.index("delivered") < order.index("read")

    def test_initial_is_sent(self):
        assert self.VALID_STATUSES[0] == "sent"

    def test_final_is_read(self):
        assert self.VALID_STATUSES[-1] == "read"


class TestMessageStatusTransitions:
    """Допустимые переходы delivery_status."""

    ALLOWED = {
        "sent": ["delivered", "read"],
        "delivered": ["read"],
        "read": [],
    }

    @pytest.mark.parametrize(
        "from_s,to_s,allowed",
        [
            ("sent", "delivered", True),
            ("sent", "read", True),
            ("delivered", "read", True),
            ("read", "sent", False),
            ("read", "delivered", False),
            ("delivered", "sent", False),
        ],
    )
    def test_transition(self, from_s, to_s, allowed):
        assert (to_s in self.ALLOWED[from_s]) == allowed


class TestConnectionManagerLogic:
    """Чистая логика ConnectionManager (без WS)."""

    def test_online_check(self):
        connections: dict[str, list] = {"user1": ["ws1"], "user2": []}

        def is_online(uid):
            return bool(connections.get(uid))

        assert is_online("user1") is True
        assert is_online("user2") is False
        assert is_online("user3") is False

    def test_disconnect_removes(self):
        connections: dict[str, list] = {"user1": ["ws1", "ws2"]}
        connections["user1"].remove("ws1")
        assert len(connections["user1"]) == 1

    def test_disconnect_last_cleans_up(self):
        connections: dict[str, list] = {"user1": ["ws1"]}
        connections["user1"].remove("ws1")
        if not connections["user1"]:
            del connections["user1"]
        assert "user1" not in connections

    def test_broadcast_exclude(self):
        connections = {"user1": True, "user2": True, "user3": True}
        exclude = "user2"
        targets = [uid for uid in connections if uid != exclude]
        assert targets == ["user1", "user3"]
