"""Validações compartilhadas pelas entidades do domínio."""

from datetime import datetime
from decimal import Decimal


def require_aware_datetime(value: datetime, field_name: str) -> None:
    """Exige data com informação de fuso horário."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} deve incluir fuso horário.")


def require_positive(value: Decimal, field_name: str) -> None:
    """Exige valor decimal estritamente positivo."""

    if value <= 0:
        raise ValueError(f"{field_name} deve ser maior que zero.")


def require_non_negative(value: Decimal, field_name: str) -> None:
    """Exige valor decimal maior ou igual a zero."""

    if value < 0:
        raise ValueError(f"{field_name} não pode ser negativo.")
