"""Формат ИНН/КПП для РФ: длина и КПП; контрольные цифры ИНН не проверяются."""

from __future__ import annotations


def digits_only(value: str | None) -> str:
    if not value:
        return ""
    return "".join(c for c in value if c.isdigit())


def kpp_format_ok(kpp: str) -> bool:
    if len(kpp) != 9 or not kpp.isdigit():
        return False
    pp = int(kpp[4:6])
    return 1 <= pp <= 99


def normalize_and_validate_partner_inn_kpp(
    partner_type: str,
    inn_raw: str,
    kpp_raw: str | None,
) -> tuple[str, str | None]:
    """
    Возвращает (inn, kpp) только цифрами.
    ValueError при несоответствии типа партнёра.
    """
    inn = digits_only(inn_raw)
    kpp = digits_only(kpp_raw) if kpp_raw else ""

    if partner_type == "individual":
        if not inn:
            return "", None
        if len(inn) in (10, 12):
            return inn, None
        raise ValueError("ИНН: 10 или 12 цифр, либо оставьте поле пустым")

    if partner_type == "legal":
        if len(inn) != 10:
            raise ValueError("ИНН юрлица: ровно 10 цифр")
        if not kpp_format_ok(kpp):
            raise ValueError("КПП: 9 цифр, код причины постановки 01–99 (позиции 5–6)")
        return inn, kpp

    if partner_type == "entrepreneur":
        if len(inn) != 12:
            raise ValueError("ИНН ИП: ровно 12 цифр")
        return inn, None

    raise ValueError("Неизвестный тип партнёра")
