"""Testes da estratégia inicial EMA + RSI + ATR."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import Candle, SignalAction
from trading_bot.strategies import EmaRsiAtrConfig, EmaRsiAtrStrategy


def candles_from_closes(*closes: int) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles: list[Candle] = []
    for index, close_value in enumerate(closes):
        close = Decimal(close_value)
        open_time = start + timedelta(minutes=index)
        candles.append(
            Candle(
                symbol="BTCUSDT",
                interval="1m",
                open_time=open_time,
                close_time=open_time + timedelta(seconds=59),
                open=close,
                high=close + Decimal(1),
                low=close - Decimal(1),
                close=close,
                volume=Decimal(10),
            )
        )
    return candles


def strategy() -> EmaRsiAtrStrategy:
    return EmaRsiAtrStrategy(
        EmaRsiAtrConfig(
            fast_ema_period=2,
            slow_ema_period=3,
            rsi_period=2,
            atr_period=2,
            buy_rsi_min=Decimal(50),
            buy_rsi_max=Decimal(80),
            sell_rsi_min=Decimal(20),
            sell_rsi_max=Decimal(50),
            stop_atr_multiple=Decimal(1),
            take_atr_multiple=Decimal(2),
        )
    )


def test_strategy_generates_buy_after_confirmed_upward_cross() -> None:
    signal = strategy().generate_signal(candles_from_closes(13, 12, 11, 14))

    assert signal.action is SignalAction.BUY
    assert signal.price == Decimal(14)
    assert signal.stop_loss == Decimal(11)
    assert signal.take_profit == Decimal(20)
    assert signal.indicators["rsi"] == Decimal(75)


def test_strategy_generates_sell_after_confirmed_downward_cross() -> None:
    signal = strategy().generate_signal(candles_from_closes(11, 12, 13, 10))

    assert signal.action is SignalAction.SELL
    assert signal.price == Decimal(10)
    assert signal.stop_loss == Decimal(13)
    assert signal.take_profit == Decimal(4)
    assert signal.indicators["rsi"].quantize(Decimal("0.01")) == Decimal("25.00")  # type: ignore[union-attr]


def test_strategy_holds_when_history_is_insufficient() -> None:
    signal = strategy().generate_signal(candles_from_closes(10, 11))

    assert signal.action is SignalAction.HOLD
    assert signal.stop_loss is None
    assert signal.take_profit is None
    assert "Histórico insuficiente" in signal.reason


def test_strategy_rejects_mixed_symbols() -> None:
    candles = candles_from_closes(13, 12, 11, 14)
    mixed = Candle(
        symbol="ETHUSDT",
        interval=candles[-1].interval,
        open_time=candles[-1].open_time,
        close_time=candles[-1].close_time,
        open=candles[-1].open,
        high=candles[-1].high,
        low=candles[-1].low,
        close=candles[-1].close,
        volume=candles[-1].volume,
    )
    candles[-1] = mixed

    with pytest.raises(ValueError, match="mesma série"):
        strategy().generate_signal(candles)


def test_strategy_configuration_rejects_fast_ema_not_faster() -> None:
    with pytest.raises(ValueError, match="EMA rápida"):
        EmaRsiAtrConfig(fast_ema_period=21, slow_ema_period=9)
