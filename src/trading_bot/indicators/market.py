"""Indicadores de contexto usados por filtros de mercado."""

from collections.abc import Sequence
from decimal import Decimal

from trading_bot.domain import Candle
from trading_bot.indicators._validation import validate_period


def sma(values: Sequence[Decimal], period: int) -> list[Decimal | None]:
    """Média móvel simples alinhada à série de entrada."""

    validate_period(period)
    result: list[Decimal | None] = [None] * len(values)
    if len(values) < period:
        return result

    window_sum = sum(values[:period], start=Decimal(0))
    decimal_period = Decimal(period)
    result[period - 1] = window_sum / decimal_period
    for index in range(period, len(values)):
        window_sum += values[index] - values[index - period]
        result[index] = window_sum / decimal_period
    return result


def rolling_vwap(
    candles: Sequence[Candle],
    period: int,
) -> list[Decimal | None]:
    """VWAP móvel calculada somente com candles já encerrados."""

    validate_period(period)
    result: list[Decimal | None] = [None] * len(candles)
    if len(candles) < period:
        return result

    weighted: list[Decimal] = []
    volumes: list[Decimal] = []
    for candle in candles:
        typical_price = (candle.high + candle.low + candle.close) / Decimal(3)
        weighted.append(typical_price * candle.volume)
        volumes.append(candle.volume)

    weighted_sum = sum(weighted[:period], start=Decimal(0))
    volume_sum = sum(volumes[:period], start=Decimal(0))
    result[period - 1] = None if volume_sum == 0 else weighted_sum / volume_sum
    for index in range(period, len(candles)):
        weighted_sum += weighted[index] - weighted[index - period]
        volume_sum += volumes[index] - volumes[index - period]
        result[index] = None if volume_sum == 0 else weighted_sum / volume_sum
    return result


def relative_volume(
    candles: Sequence[Candle],
    period: int,
) -> list[Decimal | None]:
    """Volume atual dividido pela média dos ``period`` candles anteriores."""

    validate_period(period)
    result: list[Decimal | None] = [None] * len(candles)
    if len(candles) <= period:
        return result

    volumes = [candle.volume for candle in candles]
    previous_sum = sum(volumes[:period], start=Decimal(0))
    decimal_period = Decimal(period)
    for index in range(period, len(candles)):
        average = previous_sum / decimal_period
        result[index] = None if average == 0 else volumes[index] / average
        previous_sum += volumes[index] - volumes[index - period]
    return result


def bollinger_bands(
    values: Sequence[Decimal],
    period: int,
    standard_deviations: Decimal = Decimal(2),
) -> tuple[
    list[Decimal | None],
    list[Decimal | None],
    list[Decimal | None],
]:
    """Bandas de Bollinger com desvio-padrão populacional móvel."""

    validate_period(period)
    if standard_deviations <= 0:
        raise ValueError("standard_deviations deve ser positivo.")

    middle = sma(values, period)
    upper: list[Decimal | None] = [None] * len(values)
    lower: list[Decimal | None] = [None] * len(values)
    decimal_period = Decimal(period)
    for index in range(period - 1, len(values)):
        average = middle[index]
        assert average is not None
        window = values[index - period + 1 : index + 1]
        variance = (
            sum(
                ((value - average) ** 2 for value in window),
                start=Decimal(0),
            )
            / decimal_period
        )
        deviation = variance.sqrt() * standard_deviations
        upper[index] = average + deviation
        lower[index] = average - deviation
    return middle, upper, lower
