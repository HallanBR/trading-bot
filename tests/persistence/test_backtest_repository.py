"""Testes da persistência de backtests e trades em SQLite."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.backtest import BacktestResult
from trading_bot.domain import ExitReason, PositionSide, Trade
from trading_bot.persistence import (
    BacktestNotFoundError,
    BacktestRepository,
    Database,
    PersistenceError,
)

OPENED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def winning_trade() -> Trade:
    return Trade(
        trade_id="trade-1",
        symbol="BTCUSDT",
        interval="5m",
        side=PositionSide.LONG,
        quantity=Decimal("0.123456789012345678901"),
        entry_price=Decimal("100.123456789012345678"),
        exit_price=Decimal("110.987654321098765432"),
        stop_loss=Decimal(95),
        take_profit=Decimal("110.987654321098765432"),
        fees=Decimal("0.01234567890123456789"),
        opened_at=OPENED_AT,
        closed_at=OPENED_AT + timedelta(minutes=5),
        strategy="TEST",
        exit_reason=ExitReason.TAKE_PROFIT,
    )


def backtest_result() -> BacktestResult:
    trade = winning_trade()
    initial = Decimal(1_000)
    final = initial + trade.net_pnl
    return BacktestResult(
        initial_equity=initial,
        final_equity=final,
        trades=(trade,),
        equity_curve=(initial, final),
        rejected_signals=2,
    )


def repository(path: Path) -> tuple[Database, BacktestRepository]:
    database = Database.from_path(path)
    database.create_schema()
    return database, BacktestRepository(database)


def test_save_and_load_preserve_decimals_dates_and_metrics(tmp_path: Path) -> None:
    database, backtests = repository(tmp_path / "trading.db")
    created_at = datetime(2026, 2, 1, 12, tzinfo=timezone(timedelta(hours=-3)))

    run_id = backtests.save(
        backtest_result(),
        strategy="TEST",
        symbol="BTCUSDT",
        interval="5m",
        run_id="run-1",
        created_at=created_at,
    )
    summary = backtests.get_summary(run_id)
    trades = backtests.get_trades(run_id)

    assert summary.run_id == "run-1"
    assert summary.created_at == created_at
    assert summary.final_equity == backtest_result().final_equity
    assert summary.total_trades == 1
    assert summary.wins == 1
    assert summary.rejected_signals == 2
    assert trades == [winning_trade()]
    database.dispose()


def test_data_remain_available_after_reopening_database(tmp_path: Path) -> None:
    path = tmp_path / "persistent.db"
    first_database, first_repository = repository(path)
    first_repository.save(
        backtest_result(),
        strategy="TEST",
        symbol="BTCUSDT",
        interval="5m",
        run_id="persistent-run",
    )
    first_database.dispose()

    second_database, second_repository = repository(path)

    assert second_repository.get_summary("persistent-run").total_trades == 1
    assert second_repository.get_trades("persistent-run") == [winning_trade()]
    second_database.dispose()


def test_list_summaries_orders_most_recent_first(tmp_path: Path) -> None:
    database, backtests = repository(tmp_path / "ordered.db")
    older = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = older + timedelta(days=1)
    for run_id, created_at in (("older", older), ("newer", newer)):
        backtests.save(
            backtest_result(),
            strategy="TEST",
            symbol="BTCUSDT",
            interval="5m",
            run_id=run_id,
            created_at=created_at,
        )

    summaries = backtests.list_summaries(limit=1)

    assert [summary.run_id for summary in summaries] == ["newer"]
    database.dispose()


def test_duplicate_run_rolls_back_without_creating_partial_data(
    tmp_path: Path,
) -> None:
    database, backtests = repository(tmp_path / "atomic.db")
    backtests.save(
        backtest_result(),
        strategy="TEST",
        symbol="BTCUSDT",
        interval="5m",
        run_id="duplicate",
    )

    with pytest.raises(PersistenceError):
        backtests.save(
            backtest_result(),
            strategy="TEST",
            symbol="BTCUSDT",
            interval="5m",
            run_id="duplicate",
        )

    assert len(backtests.list_summaries()) == 1
    assert len(backtests.get_trades("duplicate")) == 1
    database.dispose()


def test_missing_backtest_raises_domain_error(tmp_path: Path) -> None:
    database, backtests = repository(tmp_path / "missing.db")

    with pytest.raises(BacktestNotFoundError):
        backtests.get_summary("unknown")

    with pytest.raises(BacktestNotFoundError):
        backtests.get_trades("unknown")
    database.dispose()
