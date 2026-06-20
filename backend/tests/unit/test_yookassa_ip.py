"""Unit-тесты: app.services.yookassa_service.is_yookassa_ip."""

from __future__ import annotations

import pytest

from app.services.yookassa_service import is_yookassa_ip


@pytest.mark.parametrize(
    "ip",
    [
        "185.71.76.0",
        "185.71.76.31",
        "185.71.77.15",
        "77.75.153.0",
        "77.75.153.127",
        "77.75.156.11",
        "77.75.156.35",
        "77.75.154.128",
    ],
)
def test_ipv4_in_allowlist(ip):
    assert is_yookassa_ip(ip) is True


@pytest.mark.parametrize(
    "ip",
    [
        "8.8.8.8",
        "127.0.0.1",
        "185.71.76.32",  # сразу за /27
        "77.75.156.12",  # между /32 endpoints
        "77.75.154.127",  # перед /25
        "1.2.3.4",
    ],
)
def test_ipv4_outside_allowlist(ip):
    assert is_yookassa_ip(ip) is False


def test_ipv6_in_allowlist():
    assert is_yookassa_ip("2a02:5180::1") is True
    assert is_yookassa_ip("2a02:5180:ffff:ffff:ffff:ffff:ffff:ffff") is True


def test_ipv6_outside_allowlist():
    assert is_yookassa_ip("::1") is False
    assert is_yookassa_ip("2001:db8::1") is False


@pytest.mark.parametrize(
    "bad",
    ["", "not-an-ip", "999.999.999.999", "185.71.76", "::g::"],
)
def test_malformed_returns_false(bad):
    assert is_yookassa_ip(bad) is False
