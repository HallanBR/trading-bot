"""Testes do Average True Range."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import Candle
from trading_bot.indicators import atr, true_range


def candle(
    *,
    high: str,
    low: str,
    close: str,
    minute: int = 0,
) -> Candle:
    open_time = datetime(2026, 1, 1, 12, minute, tzinfo=timezone.utc)
    return Candle(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=open_time + timedelta(seconds=59),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(1),
    )


def test_true_range_includes_gap_from_previous_close() -> None:
    current = candle(high="15", low="13", close="14")

    assert true_range(current, previous_close=Decimal(10)) == Decimal(5)


def test_atr_uses_wilder_smoothing() -> None:
    candles = [
        candle(high="11", low="9", close="10", minute=0),
        candle(high="12", low="10", close="11", minute=1),
        candle(high="13", low="11", close="12", minute=2),
        candle(high="15", low="12", close="14", minute=3),
    ]

    result = atr(candles, period=3)

    assert result == [
        None,
        None,
        Decimal(2),
        Decimal("2.333333333333333333333333333"),
    ]


def test_atr_preserves_alignment_when_history_is_too_short() -> None:
    candles = [candle(high="11", low="9", close="10")]

    assert atr(candles, period=2) == [None]


@pytest.mark.parametrize("period", [0, -1, 1.5, True])
def test_atr_rejects_invalid_period(period: object) -> None:
    with pytest.raises(ValueError):
        atr([], period=period)  # type: ignore[arg-type]
