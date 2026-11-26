"""Подписи людей в задаче: почта не должна попадать в имя автора."""

from __future__ import annotations

from app.models.partner import Partner
from app.models.user import User
from app.services.display_names import (
    AGENT_LABEL,
    PARTNER_LABEL,
    STAFF_LABEL,
    name_from,
    partner_display_name,
    user_display_name,
)


def _user(role: str, *, email: str = "someone@example.com", full_name: str | None = None) -> User:
    return User(email=email, hashed_password="x", role=role, full_name=full_name)


def _partner(*, director_name: str, company_name: str) -> Partner:
    return Partner(
        user_id=None,
        company_name=company_name,
        director_name=director_name,
        inn="7701234567",
        phone="+71234567890",
        status="active",
    )


def test_partner_uses_director_name_then_company():
    partner = _partner(director_name="Тамара Протацкая", company_name="ИП Протацкая")
    assert partner_display_name(partner) == "Тамара Протацкая"

    only_company = _partner(director_name="   ", company_name="Юридическое бюро «Тамара»")
    assert partner_display_name(only_company) == "Юридическое бюро «Тамара»"


def test_partner_never_falls_back_to_email():
    partner_user = _user("partner", email="protatskaya.rko@gmail.com")
    name = user_display_name(partner_user, _partner(director_name="Тамара Протацкая", company_name="ИП"))
    assert name == "Тамара Протацкая"
    assert "@" not in name

    without_profile = user_display_name(partner_user)
    assert without_profile == PARTNER_LABEL


def test_staff_name_is_full_name_or_generic_label():
    named = _user("admin", email="boss@uritech.ru", full_name="  Евгений   Самсонюк ")
    assert user_display_name(named) == "Евгений Самсонюк"

    unnamed = _user("super_admin", email="ferrerokinder1978@gmail.com")
    assert user_display_name(unnamed) == STAFF_LABEL


def test_agent_and_unknown_authors():
    assert user_display_name(_user("agent")) == AGENT_LABEL
    assert user_display_name(_user("agent", full_name="Агент Иванов")) == "Агент Иванов"
    assert user_display_name(None) == "Участник"


def test_name_from_batch_lookup():
    import uuid

    user_id = uuid.uuid4()
    assert name_from({user_id: "Тамара Протацкая"}, user_id) == "Тамара Протацкая"
    assert name_from({}, user_id) is None
    assert name_from(None, user_id) is None
    assert name_from({user_id: "Тамара Протацкая"}, None) is None
