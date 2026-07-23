"""Tipos SQLAlchemy que preservam precisão e fuso horário no SQLite."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Text
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator


class DecimalText(TypeDecorator[Decimal]):
    """Armazena ``Decimal`` como texto, sem conversão intermediária para float."""

    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: Decimal | None,
        dialect: Dialect,
    ) -> str | None:
        del dialect
        return None if value is None else str(value)

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> Decimal | None:
        del dialect
        return None if value is None else Decimal(value)


class AwareDateTimeText(TypeDecorator[datetime]):
    """Armazena data UTC em ISO 8601 e restaura um ``datetime`` consciente."""

    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> str | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datas persistidas devem incluir fuso horário.")
        return value.astimezone(timezone.utc).isoformat()

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> datetime | None:
        del dialect
        if value is None:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Data persistida não possui fuso horário.")
        return parsed
