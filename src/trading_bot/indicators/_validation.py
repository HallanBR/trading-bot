"""Validações compartilhadas pelos indicadores."""


def validate_period(period: int) -> None:
    """Garante que o período seja um número inteiro positivo."""

    if isinstance(period, bool) or not isinstance(period, int) or period <= 0:
        raise ValueError("O período deve ser um número inteiro positivo.")
