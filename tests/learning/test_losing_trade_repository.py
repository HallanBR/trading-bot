"""Testes do banco isolado de casos perdedores."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import inspect

from trading_bot.domain import (
    ExitReason,
    PositionSide,
    Signal,
    SignalAction,
    Trade,
)
from trading_bot.learning import LearningDatabase, LosingTradeRepository

OPENED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def entry_signal() -> Signal:
    return Signal(
        symbol="BTCUSDT",
        interval="5m",
        action=SignalAction.BUY,
        generated_at=OPENED_AT - timedelta(minutes=5),
        price=Decimal(100),
        stop_loss=Decimal(95),
        take_profit=Decimal(110),
        strategy="EMA_RSI_ATR",
        reason="Cruzamento confirmado.",
        indicators={
            "ema_fast": Decimal("99.5"),
            "ema_slow": Decimal("99.2"),
            "rsi": Decimal("57.4"),
            "atr": Decimal("3.1"),
        },
    )


def losing_trade() -> Trade:
    return Trade(
        trade_id="paper-trade-1",
        symbol="BTCUSDT",
        interval="5m",
        side=PositionSide.LONG,
        quantity=Decimal(1),
        entry_price=Decimal(100),
        exit_price=Decimal(95),
        stop_loss=Decimal(95),
        take_profit=Decimal(110),
        fees=Decimal("0.2"),
        opened_at=OPENED_AT,
        closed_at=OPENED_AT + timedelta(minutes=10),
        strategy="EMA_RSI_ATR",
        exit_reason=ExitReason.STOP_LOSS,
        entry_signal=entry_signal(),
    )


def repository(tmp_path: Path) -> tuple[LearningDatabase, LosingTradeRepository]:
    database = LearningDatabase.from_path(tmp_path / "losing_trades.db")
    database.create_schema()
    return database, LosingTradeRepository(database)


def test_learning_database_contains_only_losing_trade_table(tmp_path: Path) -> None:
    database, _ = repository(tmp_path)

    assert inspect(database.engine).get_table_names() == ["losing_trades"]

    database.dispose()


def test_saves_loss_with_entry_indicators_and_exact_decimals(tmp_path: Path) -> None:
    database, losses = repository(tmp_path)

    assert losses.save_loss(losing_trade()) is True
    case = losses.list_recent(limit=1)[0]

    assert losses.count() == 1
    assert case.net_pnl == Decimal("-5.2")
    assert case.signal_reason == "Cruzamento confirmado."
    assert case.indicators["rsi"] == Decimal("57.4")
    assert case.indicators["atr"] == Decimal("3.1")

    database.dispose()


def test_same_loss_is_not_stored_twice(tmp_path: Path) -> None:
    database, losses = repository(tmp_path)
    trade = losing_trade()

    assert losses.save_loss(trade) is True
    assert losses.save_loss(trade) is False
    assert losses.count() == 1

    database.dispose()


def test_winning_trade_is_never_stored(tmp_path: Path) -> None:
    database, losses = repository(tmp_path)
    loss = losing_trade()
    win = Trade(
        trade_id="paper-trade-2",
        symbol=loss.symbol,
        interval=loss.interval,
        side=loss.side,
        quantity=loss.quantity,
        entry_price=loss.entry_price,
        exit_price=Decimal(110),
        stop_loss=loss.stop_loss,
        take_profit=loss.take_profit,
        fees=loss.fees,
        opened_at=loss.opened_at,
        closed_at=loss.closed_at,
        strategy=loss.strategy,
        exit_reason=ExitReason.TAKE_PROFIT,
        entry_signal=loss.entry_signal,
    )

    assert losses.save_loss(win) is False
    assert losses.count() == 0

    database.dispose()
