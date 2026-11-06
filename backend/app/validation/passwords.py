"""Ограничения пароля, накладываемые bcrypt."""

from __future__ import annotations

# bcrypt 4.x бросает ValueError, если пароль длиннее 72 байт (а не символов):
# кириллица занимает 2 байта на символ, поэтому 72 байта ≈ 36 русских букв.
BCRYPT_MAX_PASSWORD_BYTES = 72


def validate_password_bytes(value: str) -> str:
    """Не даём bcrypt упасть на слишком длинном пароле — отдаём понятную 422."""
    if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            "Пароль слишком длинный: не более 72 байт "
            "(примерно 36 символов кириллицы или 72 латиницы)",
        )
    return value
