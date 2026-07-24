"""Testes do armazenamento histórico em CSV."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.domain import Candle
from trading_bot.market_data import CandleCsvStore


def candle(index: int) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index)
    return Candle(
        symbol="BTCUSDT",
        interval="1m",
        open_time=opened,
        close_time=opened + timedelta(seconds=59, milliseconds=999),
        open=Decimal("100.10"),
        high=Decimal("102.20"),
        low=Decimal("99.90"),
        close=Decimal("101.30"),
        volume=Decimal("12.345"),
    )


def test_csv_store_round_trip_preserves_decimals(tmp_path: Path) -> None:
    path = tmp_path / "history" / "btc.csv"
    original = [candle(0), candle(1)]

    destination = CandleCsvStore().write(path, original)
    restored = CandleCsvStore().read(destination)

    assert restored == original


def test_csv_store_rejects_duplicate_open_time(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicatas"):
        CandleCsvStore().write(tmp_path / "btc.csv", [candle(0), candle(0)])
