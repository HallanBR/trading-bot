"""Testes dos indicadores de contexto de mercado."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trading_bot.domain import Candle
from trading_bot.indicators import (
    bollinger_bands,
    relative_volume,
    rolling_vwap,
    sma,
)


def candles(*volumes: int) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result: list[Candle] = []
    for index, volume in enumerate(volumes):
        price = Decimal(index + 1)
        opened = start + timedelta(minutes=index)
        result.append(
            Candle(
                symbol="BTCUSDT",
                interval="1m",
                open_time=opened,
                close_time=opened + timedelta(seconds=59),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=Decimal(volume),
            )
        )
    return result


def test_sma_is_aligned() -> None:
    assert sma([Decimal(1), Decimal(2), Decimal(3)], 2) == [
        None,
        Decimal("1.5"),
        Decimal("2.5"),
    ]


def test_relative_volume_uses_only_previous_candles() -> None:
    values = relative_volume(candles(10, 20, 45), 2)

    assert values == [None, None, Decimal(3)]


def test_rolling_vwap_uses_price_weighted_by_volume() -> None:
    values = rolling_vwap(candles(1, 3), 2)

    assert values[-1] == Decimal("1.75")


def test_bollinger_bands_return_middle_and_extremes() -> None:
    middle, upper, lower = bollinger_bands(
        [Decimal(1), Decimal(2), Decimal(3)],
        3,
        Decimal(1),
    )

    assert middle[-1] == Decimal(2)
    assert upper[-1] is not None and upper[-1] > Decimal(2)
    assert lower[-1] is not None and lower[-1] < Decimal(2)
