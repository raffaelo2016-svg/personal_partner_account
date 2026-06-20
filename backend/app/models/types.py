from datetime import UTC, datetime

from sqlalchemy.types import DateTime as SQLDateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """TIMESTAMP WITHOUT TIME ZONE, интерпретируемый как UTC на границе ORM.

    На чтение добавляет tzinfo=UTC к naive-значениям из БД — Pydantic
    тогда сериализует ISO с offset (`+00:00`), и JS-клиент парсит время
    корректно без дочитки 'Z'. На запись aware-datetime конвертируется в
    UTC и сбрасывает tzinfo, чтобы класть в существующие колонки
    TIMESTAMP (без TZ) без Alembic-миграции.
    """

    impl = SQLDateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
