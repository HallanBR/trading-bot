"""Average True Range usando a suavização de Wilder."""

from collections.abc import Sequence
from decimal import Decimal

from trading_bot.domain import Candle
from trading_bot.indicators._validation import validate_period


def true_range(candle: Candle, previous_close: Decimal | None = None) -> Decimal:
    """Calcula o True Range de um candle."""

    current_range = candle.high - candle.low
    if previous_close is None:
        return current_range

    return max(
        current_range,
        abs(candle.high - previous_close),
        abs(candle.low - previous_close),
    )


def atr(candles: Sequence[Candle], period: int = 14) -> list[Decimal | None]:
    """Calcula o ATR de Wilder, alinhado à sequência de candles."""

    validate_period(period)
    result: list[Decimal | None] = [None] * len(candles)
    if len(candles) < period:
        return result

    ranges: list[Decimal] = []
    previous_close: Decimal | None = None
    for candle in candles:
        ranges.append(true_range(candle, previous_close))
        previous_close = candle.close

    decimal_period = Decimal(period)
    previous_atr = sum(ranges[:period], start=Decimal(0)) / decimal_period
    result[period - 1] = previous_atr

    for index in range(period, len(ranges)):
        previous_atr = (
            (previous_atr * Decimal(period - 1)) + ranges[index]
        ) / decimal_period
        result[index] = previous_atr

    return result
