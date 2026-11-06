from io import BytesIO
from types import SimpleNamespace

import pytest
from docx import Document

from app.services.document_generation_service import generate_document


@pytest.fixture
def document_client():
    return SimpleNamespace(
        full_name="Иванов Иван Иванович",
        date_of_birth="1985-02-03",
        passport_series="4500",
        passport_number="123456",
        passport_issue_date="2010-04-05",
        passport_issued_by="ОВД района",
        registration_address="г. Москва, ул. Пример, д. 1",
        inn="770000000000",
        snils="123-456-789 00",
        phone="+7 900 000-00-00",
        region="Москва",
        arbitrage_court="Арбитражный суд города Москвы",
    )


@pytest.fixture
def generation_data():
    return {
        "general": {
            "birth_place": "г. Москва",
            "subdivision_code": "770-001",
            "monthly_income": "50000",
            "cash_amount": "15000",
            "document_date": "2026-10-01",
        },
        "creditors": [
            {
                "number": "1.1",
                "obligation": "Кредит",
                "name": "ПАО «Банк»",
                "address": "г. Москва",
                "basis": "Кредитный договор",
                "contract_number": "123",
                "contract_date": "2020-01-01",
                "total_amount": "750000",
                "overdue_amount": "100000",
                "penalties": "5000",
            }
        ],
        "real_estate": [
            {
                "category": "apartment",
                "name": "2-комнатная квартира",
                "ownership": "1/2 доли",
                "address": "г. Москва",
                "area": "54",
                "basis_value": "Купля-продажа, 6 000 000",
                "pledge": "ПАО «Банк»",
            }
        ],
    }


@pytest.mark.parametrize("kind", ["application", "creditors", "inventory"])
def test_generates_valid_docx(kind, document_client, generation_data):
    content = generate_document(kind, document_client, generation_data)
    document = Document(BytesIO(content))

    assert content.startswith(b"PK")
    assert len(document.sections) >= 1
    assert document.tables


def test_application_contains_client_and_total(document_client, generation_data):
    document = Document(BytesIO(generate_document("application", document_client, generation_data)))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert "Иванов Иван Иванович" in text
    assert "750 000" in text


def test_inventory_keeps_landscape_section(document_client, generation_data):
    document = Document(BytesIO(generate_document("inventory", document_client, generation_data)))

    assert len(document.sections) == 2
    assert document.sections[1].page_width > document.sections[1].page_height
    assert "2-комнатная квартира" in document.tables[1].rows[7].cells[1].text
