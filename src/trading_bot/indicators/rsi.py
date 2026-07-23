"""Índice de força relativa usando a suavização de Wilder."""

from collections.abc import Sequence
from decimal import Decimal

from trading_bot.indicators._validation import validate_period

HUNDRED = Decimal(100)
NEUTRAL_RSI = Decimal(50)


def rsi(values: Sequence[Decimal], period: int = 14) -> list[Decimal | None]:
    """Calcula o RSI de Wilder, alinhado à série de entrada."""

    validate_period(period)
    result: list[Decimal | None] = [None] * len(values)
    if len(values) <= period:
        return result

    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for index in range(1, period + 1):
        gain, loss = _gain_and_loss(values[index] - values[index - 1])
        gains.append(gain)
        losses.append(loss)

    decimal_period = Decimal(period)
    average_gain = sum(gains, start=Decimal(0)) / decimal_period
    average_loss = sum(losses, start=Decimal(0)) / decimal_period
    result[period] = _to_rsi(average_gain, average_loss)

    for index in range(period + 1, len(values)):
        gain, loss = _gain_and_loss(values[index] - values[index - 1])
        average_gain = ((average_gain * Decimal(period - 1)) + gain) / decimal_period
        average_loss = ((average_loss * Decimal(period - 1)) + loss) / decimal_period
        result[index] = _to_rsi(average_gain, average_loss)

    return result


def _gain_and_loss(change: Decimal) -> tuple[Decimal, Decimal]:
    if change > 0:
        return change, Decimal(0)
    if change < 0:
        return Decimal(0), -change
    return Decimal(0), Decimal(0)


def _to_rsi(average_gain: Decimal, average_loss: Decimal) -> Decimal:
    if average_gain == 0 and average_loss == 0:
        return NEUTRAL_RSI
    if average_loss == 0:
        return HUNDRED
    if average_gain == 0:
        return Decimal(0)

    relative_strength = average_gain / average_loss
    return HUNDRED - (HUNDRED / (Decimal(1) + relative_strength))
