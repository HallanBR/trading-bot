"""Testes do dimensionamento de posição."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import Signal, SignalAction
from trading_bot.risk import calculate_position_size


def buy_signal() -> Signal:
    return Signal(
        symbol="BTCUSDT",
        interval="5m",
        action=SignalAction.BUY,
        generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        price=Decimal(100),
        stop_loss=Decimal(95),
        take_profit=Decimal(110),
        strategy="TEST",
        reason="Entrada de teste.",
    )


def test_position_size_risks_fixed_fraction_of_equity() -> None:
    result = calculate_position_size(
        buy_signal(),
        account_equity=Decimal(10_000),
        risk_fraction=Decimal("0.01"),
        max_position_fraction=Decimal("0.25"),
    )

    assert result.quantity == Decimal(20)
    assert result.risk_amount == Decimal(100)
    assert result.notional == Decimal(2_000)


def test_position_size_respects_notional_cap() -> None:
    result = calculate_position_size(
        buy_signal(),
        account_equity=Decimal(10_000),
        risk_fraction=Decimal("0.01"),
        max_position_fraction=Decimal("0.10"),
    )

    assert result.quantity == Decimal(10)
    assert result.risk_amount == Decimal(50)
    assert result.notional == Decimal(1_000)


def test_position_size_respects_absolute_notional_cap() -> None:
    result = calculate_position_size(
        buy_signal(),
        account_equity=Decimal(10_000),
        risk_fraction=Decimal("0.01"),
        max_position_fraction=Decimal("0.25"),
        max_position_notional=Decimal(10),
    )

    assert result.quantity == Decimal("0.1")
    assert result.risk_amount == Decimal("0.5")
    assert result.notional == Decimal(10)


def test_position_size_rejects_hold_signal() -> None:
    hold = Signal(
        symbol="BTCUSDT",
        interval="5m",
        action=SignalAction.HOLD,
        generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        price=Decimal(100),
        strategy="TEST",
        reason="Sem entrada.",
    )

    with pytest.raises(ValueError, match="HOLD"):
        calculate_position_size(
            hold,
            account_equity=Decimal(10_000),
            risk_fraction=Decimal("0.01"),
            max_position_fraction=Decimal("0.25"),
        )
