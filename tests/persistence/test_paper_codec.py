"""Testes da serialização versionada do estado paper."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import Candle, Signal, SignalAction
from trading_bot.execution import PaperExecutorState
from trading_bot.persistence.paper_codec import dump_paper_state, load_paper_state
from trading_bot.trading import PaperTradingState

OPEN_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def candle() -> Candle:
    return Candle(
        symbol="BTCUSDT",
        interval="1m",
        open_time=OPEN_TIME,
        close_time=OPEN_TIME + timedelta(seconds=59),
        open=Decimal("100.123456789012345678"),
        high=Decimal(102),
        low=Decimal(99),
        close=Decimal(101),
        volume=Decimal("42.5"),
    )


def signal() -> Signal:
    return Signal(
        symbol="BTCUSDT",
        interval="1m",
        action=SignalAction.BUY,
        generated_at=candle().close_time,
        price=Decimal(101),
        strategy="TEST",
        reason="Sinal persistido.",
        stop_loss=Decimal(99),
        take_profit=Decimal(105),
        indicators={"rsi": Decimal("56.789"), "atr": None},
    )


def state() -> PaperTradingState:
    return PaperTradingState(
        strategy_name="TEST",
        max_history=300,
        initialized=True,
        history=(candle(),),
        last_processed_open_time=OPEN_TIME,
        executor=PaperExecutorState(
            equity=Decimal("9987.654321"),
            pending_signal=signal(),
            open_position=None,
            current_day=OPEN_TIME.date(),
            day_start_equity=Decimal(10_000),
            daily_net_pnl=Decimal("-12.345679"),
            trades_today=1,
            consecutive_losses=1,
            rejected_signals=2,
            position_number=1,
        ),
    )


def test_checkpoint_round_trip_preserves_decimals_and_signal() -> None:
    original = state()

    restored = load_paper_state(dump_paper_state(original))

    assert restored == original
    assert restored.executor.pending_signal is not None
    assert restored.executor.pending_signal.indicators["rsi"] == Decimal("56.789")


def test_checkpoint_rejects_unknown_schema_version() -> None:
    payload = json.loads(dump_paper_state(state()))
    payload["schema_version"] = 999

    with pytest.raises(ValueError, match="não suportada"):
        load_paper_state(json.dumps(payload))
