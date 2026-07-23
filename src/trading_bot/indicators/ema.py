"""Média móvel exponencial."""

from collections.abc import Sequence
from decimal import Decimal

from trading_bot.indicators._validation import validate_period


def ema(values: Sequence[Decimal], period: int) -> list[Decimal | None]:
    """Calcula a EMA sem antecipar valores anteriores ao período inicial.

    A primeira EMA é a média aritmética dos ``period`` primeiros valores. Os
    índices anteriores permanecem como ``None`` para manter o resultado
    alinhado à série de entrada.
    """

    validate_period(period)
    result: list[Decimal | None] = [None] * len(values)
    if len(values) < period:
        return result

    decimal_period = Decimal(period)
    multiplier = Decimal(2) / Decimal(period + 1)
    previous = sum(values[:period], start=Decimal(0)) / decimal_period
    result[period - 1] = previous

    for index in range(period, len(values)):
        previous = ((values[index] - previous) * multiplier) + previous
        result[index] = previous

    return result
