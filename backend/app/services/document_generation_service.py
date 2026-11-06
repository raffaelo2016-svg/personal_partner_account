from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

from docx import Document
from docx.document import Document as DocxDocument
from docx.table import _Cell, _Row
from docx.text.paragraph import Paragraph

DocumentKind = Literal["application", "creditors", "inventory"]

DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates" / "legal_documents"
DOCUMENT_FILENAMES: dict[DocumentKind, str] = {
    "application": "Заявление в суд.docx",
    "creditors": "Список кредиторов и должников.docx",
    "inventory": "Опись имущества.docx",
}

_MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def _value(source: Any, name: str, default: Any = "") -> Any:
    value = source.get(name, default) if isinstance(source, Mapping) else getattr(source, name, default)
    return default if value is None else value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _items(data: Mapping[str, Any], name: str) -> list[Mapping[str, Any]]:
    value = data.get(name, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _text(value: Any, fallback: str = "не указано") -> str:
    rendered = str(value or "").strip()
    return rendered or fallback


def _date(value: Any) -> str:
    if isinstance(value, date | datetime):
        return value.strftime("%d.%m.%Y")
    rendered = str(value or "").strip()
    if not rendered:
        return "не указано"
    try:
        return date.fromisoformat(rendered[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return rendered


def _document_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return date.today()


def _long_date(value: Any) -> str:
    parsed = _document_date(value)
    return f"«{parsed.day}» {_MONTHS[parsed.month - 1]} {parsed.year} г."


def _decimal(value: Any) -> Decimal:
    normalized = str(value or "0").replace(" ", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return Decimal(0)


def _money(value: Any) -> str:
    amount = _decimal(value)
    if amount == amount.to_integral():
        return f"{int(amount):,}".replace(",", " ")
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


def _set_paragraph(paragraph: Paragraph, text: str) -> None:
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


def _set_cell(cell: _Cell, text: str) -> None:
    _set_paragraph(cell.paragraphs[0], text)
    for paragraph in cell.paragraphs[1:]:
        _set_paragraph(paragraph, "")


def _distinct_cells(row: _Row) -> list[_Cell]:
    cells: list[_Cell] = []
    seen: set[int] = set()
    for cell in row.cells:
        identity = id(cell._tc)
        if identity not in seen:
            seen.add(identity)
            cells.append(cell)
    return cells


def _fill_row(row: _Row, values: Iterable[Any]) -> None:
    for cell, value in zip(_distinct_cells(row), values, strict=False):
        _set_cell(cell, str(value or ""))


def _split_name(full_name: str) -> tuple[str, str, str]:
    parts = full_name.split()
    return (
        parts[0] if parts else "",
        parts[1] if len(parts) > 1 else "",
        " ".join(parts[2:]) if len(parts) > 2 else "",
    )


def _passport(client: Any) -> str:
    return " ".join(
        part
        for part in (_text(_value(client, "passport_series"), ""), _text(_value(client, "passport_number"), ""))
        if part
    )


def _identity_values(client: Any, general: Mapping[str, Any]) -> dict[int, str]:
    surname, name, patronymic = _split_name(_text(_value(client, "full_name"), ""))
    return {
        1: surname,
        2: name,
        3: patronymic,
        4: _text(general.get("previous_names"), "Фамилию, имя, отчество не изменял(а)"),
        5: _date(_value(client, "date_of_birth")),
        6: _text(general.get("birth_place")),
        7: _text(_value(client, "snils")),
        8: _text(_value(client, "inn")),
        10: "Паспорт гражданина РФ",
        11: _text(_passport(client)),
        13: _text(_value(client, "region")),
        17: _text(_value(client, "registration_address")),
    }


def _fill_identity_table(document: DocxDocument, client: Any, general: Mapping[str, Any]) -> None:
    table = document.tables[0]
    for row_index, value in _identity_values(client, general).items():
        cells = _distinct_cells(table.rows[row_index])
        if len(cells) >= 3:
            _set_cell(cells[2], value)


def _joined(items: list[Mapping[str, Any]], field: str, *, default: str = "") -> str:
    values = [_text(item.get(field), "") for item in items]
    values = [value for value in values if value]
    return "\n".join(values) or default


def _basis(item: Mapping[str, Any]) -> str:
    parts = [
        _text(item.get("basis"), ""),
        f"№ {_text(item.get('contract_number'), '')}" if item.get("contract_number") else "",
        f"от {_date(item.get('contract_date'))}" if item.get("contract_date") else "",
    ]
    return " ".join(part for part in parts if part) or "не указано"


def _has_assets(data: Mapping[str, Any]) -> bool:
    return any(
        _items(data, key)
        for key in ("real_estate", "vehicles", "bank_accounts", "company_interests", "securities", "other_assets")
    )


def _generate_application(document: DocxDocument, client: Any, data: Mapping[str, Any]) -> None:
    general = _mapping(data.get("general"))
    creditors = _items(data, "creditors")
    accounts = _items(data, "bank_accounts")
    total = sum((_decimal(item.get("total_amount")) for item in creditors), Decimal(0))
    overdue = sum((_decimal(item.get("overdue_amount")) for item in creditors), Decimal(0))
    full_name = _text(_value(client, "full_name"))
    registration = _text(_value(client, "registration_address"))
    birth_place = _text(general.get("birth_place"))
    cash = _money(general.get("cash_amount"))
    monthly_income = _money(general.get("monthly_income"))

    replacements = {
        0: f"В {_text(_value(client, 'arbitrage_court'))}",
        2: f"Заявитель (Должник): {full_name}",
        3: f"{_date(_value(client, 'date_of_birth'))} года рождения",
        4: f"Место рождения: {birth_place}",
        5: f"Паспорт: № {_text(_passport(client))}",
        6: f"Выдан: {_text(_value(client, 'passport_issued_by'))}",
        7: f"Дата выдачи: {_date(_value(client, 'passport_issue_date'))}",
        8: f"Код подразделения: {_text(general.get('subdivision_code'))}",
        9: f"Место регистрации: {registration}",
        10: f"Фактическое место жительства: {_text(general.get('actual_address'), registration)}",
        11: f"СНИЛС: {_text(_value(client, 'snils'))}",
        12: f"ИНН: {_text(_value(client, 'inn'))}",
        13: f"Телефон: {_text(_value(client, 'phone'))}",
        22: (
            f"Я, {full_name}, обращаюсь в суд с заявлением о признании меня банкротом, "
            "поскольку имею неисполненные денежные обязательства."
        ),
        23: f"Общий размер требований кредиторов по данным заявителя составляет {_money(total)} рублей.",
        24: f"Обстоятельства и цели возникновения обязательств: {_text(general.get('credit_purpose'))}.",
        25: f"Указанный заявителем среднемесячный доход составляет {monthly_income} рублей.",
        27: f"Сведения о предъявленных исковых требованиях: {_text(general.get('claims_present'))}.",
        28: (
            f"Сведения о судебных решениях и исполнительных производствах: {_text(general.get('enforcement_present'))}."
        ),
        30: (
            "Сведения о долговых расписках и неисполненных денежных требованиях: "
            f"{_text(general.get('other_obligations'))}."
        ),
        32: "Сведения об имуществе приведены в прилагаемой описи имущества."
        if _has_assets(data)
        else "По данным заявителя имущество, подлежащее отражению в описи, отсутствует.",
        33: f"Наличные денежные средства: {cash} рублей.",
        34: f"Сведения о сделках за три года до даты подачи заявления: {_text(general.get('transactions_present'))}.",
        35: (
            "Соотношение доходов, имущества и обязательств заявителя отражено в настоящем "
            "заявлении и прилагаемых документах."
        ),
        36: "Оценка финансового положения производится на основании указанных сведений и приложенных доказательств.",
        37: (
            f"Семейное положение: {_text(general.get('marital_status'))}. "
            f"Лица на иждивении: {_text(general.get('dependants'))}."
        ),
        38: f"Сведения о занятости: {_text(general.get('employment_status'))}.",
        40: "- заявитель прекратил(а) исполнение денежных обязательств, срок исполнения которых наступил;",
        41: "- сведения о просроченных обязательствах приведены в списке кредиторов и должников;",
        42: f"Размер денежных обязательств по данным заявителя составляет {_money(total)} рублей.",
        43: f"Просроченная сумма задолженности по данным заявителя составляет {_money(overdue)} рублей.",
        45: "Сведения о счетах и банковских картах:",
        46: _format_accounts(accounts),
        47: (
            "Сведения об ответственности за экономические правонарушения: "
            f"{_text(general.get('criminal_economic_record'))}."
        ),
        48: (
            "Сведения о наличии или отсутствии судимости и уголовного преследования "
            "подтверждаются прилагаемыми документами."
        ),
        54: f"Сведения о признании банкротом в течение пяти лет: {_text(general.get('bankruptcy_last_five_years'))}.",
        57: f"{_money(total)} ÷ (12 месяцев × 3) = {_money(total / Decimal(36))} руб. в месяц.",
        63: (
            f"1. Признать гражданина Российской Федерации {full_name}, "
            f"{_date(_value(client, 'date_of_birth'))} года рождения, "
            f"место рождения: {birth_place}, паспорт: № {_text(_passport(client))}, "
            f"выдан: {_text(_value(client, 'passport_issued_by'))}, "
            f"дата выдачи: {_date(_value(client, 'passport_issue_date'))}, "
            f"код подразделения: {_text(general.get('subdivision_code'))}, "
            f"место жительства по регистрации: {registration}, несостоятельным (банкротом)."
        ),
        78: f"{full_name}  Подпись________________",
    }
    for index, value in replacements.items():
        _set_paragraph(document.paragraphs[index], value)

    summaries = []
    for index, creditor in enumerate(creditors, 1):
        summaries.append(
            f"{index}. {_text(creditor.get('name'))}: {_money(creditor.get('total_amount'))} руб.; {_basis(creditor)}"
        )
    if document.tables and len(document.tables) > 1:
        rows = document.tables[1].rows
        if rows:
            _set_cell(rows[0].cells[0], summaries[0] if summaries else "Кредиторы не указаны")
        if len(rows) > 1:
            _set_cell(rows[1].cells[0], "\n".join(summaries[1:]))


def _format_accounts(accounts: list[Mapping[str, Any]]) -> str:
    if not accounts:
        return "Банковские счета не указаны."
    return "\n".join(
        f"{index}. {_text(item.get('bank'))}; {_text(item.get('account_type'))}; "
        f"валюта: {_text(item.get('currency'))}; остаток: {_money(item.get('balance'))}"
        for index, item in enumerate(accounts, 1)
    )


def _generate_creditors(document: DocxDocument, client: Any, data: Mapping[str, Any]) -> None:
    general = _mapping(data.get("general"))
    creditors = _items(data, "creditors")
    debtors = _items(data, "debtors")
    _fill_identity_table(document, client, general)

    if len(document.tables) > 1:
        values = (
            _joined(creditors, "number", default="1"),
            _joined(creditors, "obligation", default="не указано"),
            _joined(creditors, "name", default="не указано"),
            _joined(creditors, "address", default="не указано"),
            "\n".join(_basis(item) for item in creditors) or "не указано",
            "\n".join(_money(item.get("total_amount")) for item in creditors) or "0",
            "\n".join(_money(item.get("overdue_amount")) for item in creditors) or "0",
            "\n".join(_money(item.get("penalties")) for item in creditors) or "0",
        )
        _fill_row(document.tables[1].rows[4], values)

    if len(document.tables) > 5:
        for row_index, debtor in enumerate(debtors[:3], 4):
            _fill_row(
                document.tables[5].rows[row_index],
                (
                    f"1.{row_index - 3}",
                    _text(debtor.get("obligation")),
                    _text(debtor.get("name")),
                    _text(debtor.get("address")),
                    _basis(debtor),
                    _money(debtor.get("total_amount")),
                    _money(debtor.get("overdue_amount")),
                    _money(debtor.get("penalties")),
                ),
            )

    if len(document.tables) > 9:
        signature = document.tables[9]
        _fill_row(signature.rows[0], ("", _long_date(general.get("document_date")), "", "", "", ""))
        row = _distinct_cells(signature.rows[1])
        if row:
            _set_cell(row[-1], _text(_value(client, "full_name")))


def _grouped_lines(items: list[Mapping[str, Any]], fields: tuple[str, ...]) -> list[str]:
    return ["; ".join(_text(item.get(field), "") for field in fields).strip("; ") for item in items]


def _fill_category_row(row: _Row, items: list[Mapping[str, Any]], fields: tuple[str, ...], *, number: str) -> None:
    columns = [[number]]
    for field_index in range(len(fields)):
        columns.append([_text(item.get(fields[field_index]), "") for item in items])
    _fill_row(row, ["\n".join(value for value in column if value) for column in columns])


def _generate_inventory(document: DocxDocument, client: Any, data: Mapping[str, Any]) -> None:
    general = _mapping(data.get("general"))
    _fill_identity_table(document, client, general)

    real_estate = _items(data, "real_estate")
    real_rows = {
        "land": (3, "1.1"),
        "house": (5, "1.2"),
        "apartment": (7, "1.3"),
        "garage": (9, "1.4"),
        "other": (11, "1.5"),
    }
    for category, (row_index, number) in real_rows.items():
        entries = [item for item in real_estate if item.get("category") == category]
        if entries:
            _fill_category_row(
                document.tables[1].rows[row_index],
                entries,
                ("name", "ownership", "address", "area", "basis_value", "pledge"),
                number=number,
            )

    vehicles = _items(data, "vehicles")
    vehicle_rows = {
        "car": (3, "2.1"),
        "truck": (5, "2.2"),
        "motorcycle": (7, "2.3"),
        "agriculture": (9, "2.4"),
        "water": (11, "2.5"),
        "air": (13, "2.6"),
        "other": (15, "2.7"),
    }
    for category, (row_index, number) in vehicle_rows.items():
        entries = [item for item in vehicles if item.get("category") == category]
        if entries:
            _fill_category_row(
                document.tables[2].rows[row_index],
                entries,
                ("name", "identifier", "ownership", "address", "value", "pledge"),
                number=number,
            )

    accounts = _items(data, "bank_accounts")
    if accounts:
        _fill_row(
            document.tables[2].rows[20],
            (
                "",
                "\n".join(_text(item.get("bank")) for item in accounts),
                "\n".join(f"{_text(item.get('account_type'))}, {_text(item.get('currency'))}" for item in accounts),
                "\n".join(_date(item.get("opened_at")) for item in accounts),
                "\n".join(_money(item.get("balance")) for item in accounts),
            ),
        )

    for row_index, item in zip((23, 24, 25), _items(data, "company_interests")[:3], strict=False):
        _fill_row(
            document.tables[2].rows[row_index],
            (
                f"4.{row_index - 22}",
                _text(item.get("name")),
                _text(item.get("address")),
                _text(item.get("capital")),
                _text(item.get("share")),
                _text(item.get("basis")),
            ),
        )

    for row_index, item in zip((28, 29, 30), _items(data, "securities")[:3], strict=False):
        _fill_row(
            document.tables[2].rows[row_index],
            (
                f"5.{row_index - 27}",
                _text(item.get("type")),
                _text(item.get("issuer")),
                _money(item.get("nominal")),
                _text(item.get("quantity")),
                _money(item.get("total")),
            ),
        )

    other_assets = _items(data, "other_assets")
    other_rows = {
        "cash": (33, "6.1"),
        "jewelry": (35, "6.2"),
        "art": (37, "6.3"),
        "professional": (39, "6.4"),
        "other": (41, "6.5"),
    }
    if general.get("cash_amount") and not any(item.get("category") == "cash" for item in other_assets):
        other_assets.append({"category": "cash", "name": "Наличные денежные средства", "value": general["cash_amount"]})
    for category, (row_index, number) in other_rows.items():
        entries = [item for item in other_assets if item.get("category") == category]
        if entries:
            _fill_category_row(
                document.tables[2].rows[row_index],
                entries,
                ("name", "value", "address", "pledge"),
                number=number,
            )

    signature = document.tables[3]
    _fill_row(signature.rows[0], (_long_date(general.get("document_date")), "", "", ""))
    row = _distinct_cells(signature.rows[1])
    if row:
        _set_cell(row[-1], _text(_value(client, "full_name")))


def generate_document(kind: DocumentKind, client: Any, data: Mapping[str, Any] | None = None) -> bytes:
    """Render a client document from an approved DOCX template without changing its page setup."""
    payload = _mapping(data or _value(client, "document_generation_data", {}))
    document = Document(TEMPLATES_DIR / f"{kind}.docx")
    if kind == "application":
        _generate_application(document, client, payload)
    elif kind == "creditors":
        _generate_creditors(document, client, payload)
    else:
        _generate_inventory(document, client, payload)

    output = BytesIO()
    document.save(output)
    return output.getvalue()
