"""Testes do modelo de sinal."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import Signal, SignalAction


def signal(**overrides: object) -> Signal:
    values: dict[str, object] = {
        "symbol": "BTCUSDT",
        "interval": "5m",
        "action": SignalAction.BUY,
        "generated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "price": Decimal(100),
        "stop_loss": Decimal(95),
        "take_profit": Decimal(110),
        "strategy": "TEST",
        "reason": "Cruzamento confirmado.",
        "indicators": {"rsi": Decimal(55)},
    }
    values.update(overrides)
    return Signal(**values)  # type: ignore[arg-type]


def test_buy_signal_accepts_valid_price_levels() -> None:
    result = signal()

    assert result.action is SignalAction.BUY
    assert result.stop_loss < result.price < result.take_profit  # type: ignore[operator]
    assert result.indicators["rsi"] == Decimal(55)


def test_hold_signal_cannot_define_stop_or_target() -> None:
    with pytest.raises(ValueError, match="HOLD"):
        signal(action=SignalAction.HOLD)


def test_buy_signal_rejects_inverted_price_levels() -> None:
    with pytest.raises(ValueError, match="ordem inválida"):
        signal(stop_loss=Decimal(105))


def test_signal_requires_timezone() -> None:
    with pytest.raises(ValueError, match="fuso horário"):
        signal(generated_at=datetime(2026, 1, 1))  # noqa: DTZ001
