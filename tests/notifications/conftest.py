"""Fixtures compartilhadas dos testes de notificação."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import ExitReason, PositionSide, Trade


@pytest.fixture
def winning_trade() -> Trade:
    opened_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Trade(
        trade_id="trade-1",
        symbol="BTCUSDT",
        interval="5m",
        side=PositionSide.LONG,
        quantity=Decimal(1),
        entry_price=Decimal(100),
        exit_price=Decimal(110),
        stop_loss=Decimal(95),
        take_profit=Decimal(110),
        fees=Decimal(1),
        opened_at=opened_at,
        closed_at=opened_at + timedelta(minutes=5),
        strategy="EMA_RSI_ATR",
        exit_reason=ExitReason.TAKE_PROFIT,
    )
