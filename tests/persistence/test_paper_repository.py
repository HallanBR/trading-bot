"""Testes da persistência transacional das sessões paper."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.domain import (
    Candle,
    ExitReason,
    PositionSide,
    Signal,
    SignalAction,
    Trade,
)
from trading_bot.execution import PaperExecutorState
from trading_bot.persistence import (
    Database,
    PaperSessionRepository,
    PersistenceError,
    build_paper_session_id,
)
from trading_bot.trading import PaperTradingState

OPEN_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
SESSION_ID = build_paper_session_id("BTCUSDT", "1m", "TEST")


def candle() -> Candle:
    return Candle(
        symbol="BTCUSDT",
        interval="1m",
        open_time=OPEN_TIME,
        close_time=OPEN_TIME + timedelta(seconds=59),
        open=Decimal(100),
        high=Decimal(102),
        low=Decimal(98),
        close=Decimal(101),
        volume=Decimal(10),
    )


def entry_signal(*, symbol: str = "BTCUSDT") -> Signal:
    return Signal(
        symbol=symbol,
        interval="1m",
        action=SignalAction.BUY,
        generated_at=candle().close_time,
        price=Decimal(100),
        stop_loss=Decimal(95),
        take_profit=Decimal(110),
        strategy="TEST",
        reason="Contexto completo.",
        indicators={"rsi": Decimal(55)},
    )


def state(*, equity: str = "1000") -> PaperTradingState:
    return PaperTradingState(
        strategy_name="TEST",
        max_history=300,
        initialized=True,
        history=(candle(),),
        last_processed_open_time=OPEN_TIME,
        executor=PaperExecutorState(
            equity=Decimal(equity),
            pending_signal=entry_signal(),
            open_position=None,
            current_day=OPEN_TIME.date(),
            day_start_equity=Decimal(1_000),
            daily_net_pnl=Decimal(equity) - Decimal(1_000),
            trades_today=0,
            consecutive_losses=0,
            rejected_signals=0,
            position_number=0,
        ),
    )


def trade(
    trade_id: str,
    *,
    exit_price: str,
    reason: ExitReason,
    symbol: str = "BTCUSDT",
    close_after_minutes: int = 5,
) -> Trade:
    return Trade(
        trade_id=trade_id,
        symbol=symbol,
        interval="1m",
        side=PositionSide.LONG,
        quantity=Decimal(1),
        entry_price=Decimal(100),
        exit_price=Decimal(exit_price),
        stop_loss=Decimal(95),
        take_profit=Decimal(110),
        fees=Decimal("0.2"),
        opened_at=OPEN_TIME,
        closed_at=OPEN_TIME + timedelta(minutes=close_after_minutes),
        strategy="TEST",
        exit_reason=reason,
        entry_signal=entry_signal(symbol=symbol),
    )


def repository(path: Path) -> tuple[Database, PaperSessionRepository]:
    database = Database.from_path(path)
    database.create_schema()
    return database, PaperSessionRepository(database)


def test_checkpoint_remains_available_after_reopening(tmp_path: Path) -> None:
    path = tmp_path / "paper.db"
    first_database, first = repository(path)
    first.save_checkpoint(SESSION_ID, state())
    first_database.dispose()
    second_database, second = repository(path)

    assert second.load_state(SESSION_ID) == state()

    second_database.dispose()


def test_all_trade_results_are_recorded_and_reconstructed(tmp_path: Path) -> None:
    database, sessions = repository(tmp_path / "trades.db")
    win = trade(
        "paper-trade-1",
        exit_price="110",
        reason=ExitReason.TAKE_PROFIT,
    )
    loss = trade(
        "paper-trade-2",
        exit_price="95",
        reason=ExitReason.STOP_LOSS,
        close_after_minutes=6,
    )

    inserted = sessions.save_checkpoint(SESSION_ID, state(), [win, loss])
    counts = sessions.trade_counts(SESSION_ID)

    assert inserted == 2
    assert counts.total == 2
    assert counts.wins == 1
    assert counts.losses == 1
    assert sessions.list_trades(SESSION_ID) == [loss, win]
    database.dispose()


def test_replayed_trade_is_not_inserted_twice(tmp_path: Path) -> None:
    database, sessions = repository(tmp_path / "deduplicated.db")
    loss = trade(
        "paper-trade-1",
        exit_price="95",
        reason=ExitReason.STOP_LOSS,
    )

    assert sessions.save_checkpoint(SESSION_ID, state(), [loss]) == 1
    assert sessions.save_checkpoint(SESSION_ID, state(), [loss]) == 0
    assert sessions.trade_counts(SESSION_ID).total == 1
    database.dispose()


def test_unrelated_trade_rolls_back_checkpoint(tmp_path: Path) -> None:
    database, sessions = repository(tmp_path / "atomic.db")
    original = state()
    sessions.save_checkpoint(SESSION_ID, original)
    unrelated = trade(
        "paper-trade-1",
        exit_price="95",
        reason=ExitReason.STOP_LOSS,
        symbol="ETHUSDT",
    )

    with pytest.raises(PersistenceError):
        sessions.save_checkpoint(SESSION_ID, state(equity="900"), [unrelated])

    assert sessions.load_state(SESSION_ID) == original
    assert sessions.trade_counts(SESSION_ID).total == 0
    database.dispose()
