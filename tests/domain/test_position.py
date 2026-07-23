"""Testes do modelo de posição."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import Position, PositionSide


def position(**overrides: object) -> Position:
    values: dict[str, object] = {
        "position_id": "position-1",
        "symbol": "BTCUSDT",
        "interval": "5m",
        "side": PositionSide.LONG,
        "quantity": Decimal("0.01"),
        "entry_price": Decimal(100),
        "stop_loss": Decimal(95),
        "take_profit": Decimal(110),
        "opened_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "strategy": "TEST",
    }
    values.update(overrides)
    return Position(**values)  # type: ignore[arg-type]


def test_short_position_accepts_reversed_exit_levels() -> None:
    result = position(
        side=PositionSide.SHORT,
        stop_loss=Decimal(105),
        take_profit=Decimal(90),
    )

    assert result.take_profit < result.entry_price < result.stop_loss


def test_position_rejects_zero_quantity() -> None:
    with pytest.raises(ValueError, match="quantity"):
        position(quantity=Decimal(0))


def test_position_rejects_invalid_long_levels() -> None:
    with pytest.raises(ValueError, match="ordem inválida"):
        position(take_profit=Decimal(90))
