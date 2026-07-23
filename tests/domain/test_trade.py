"""Testes do modelo de operação encerrada."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import (
    ExitReason,
    PositionSide,
    Trade,
    TradeResult,
)

OPENED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def trade(**overrides: object) -> Trade:
    values: dict[str, object] = {
        "trade_id": "trade-1",
        "symbol": "BTCUSDT",
        "interval": "5m",
        "side": PositionSide.LONG,
        "quantity": Decimal(2),
        "entry_price": Decimal(100),
        "exit_price": Decimal(110),
        "fees": Decimal(1),
        "opened_at": OPENED_AT,
        "closed_at": OPENED_AT + timedelta(minutes=5),
        "strategy": "TEST",
        "exit_reason": ExitReason.TAKE_PROFIT,
    }
    values.update(overrides)
    return Trade(**values)  # type: ignore[arg-type]


def test_long_trade_calculates_net_profit_after_fees() -> None:
    result = trade()

    assert result.gross_pnl == Decimal(20)
    assert result.net_pnl == Decimal(19)
    assert result.result is TradeResult.WIN


def test_short_trade_profits_when_exit_is_lower() -> None:
    result = trade(
        side=PositionSide.SHORT,
        exit_price=Decimal(90),
        fees=Decimal(2),
    )

    assert result.gross_pnl == Decimal(20)
    assert result.net_pnl == Decimal(18)
    assert result.result is TradeResult.WIN


def test_fees_can_turn_gross_profit_into_net_loss() -> None:
    result = trade(exit_price=Decimal(101), fees=Decimal(3))

    assert result.gross_pnl == Decimal(2)
    assert result.net_pnl == Decimal(-1)
    assert result.result is TradeResult.LOSS


def test_trade_rejects_close_before_open() -> None:
    with pytest.raises(ValueError, match="closed_at"):
        trade(closed_at=OPENED_AT - timedelta(seconds=1))
