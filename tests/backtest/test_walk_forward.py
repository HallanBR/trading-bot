"""Testes da separação temporal walk-forward."""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trading_bot.backtest import (
    BacktestConfig,
    WalkForwardConfig,
    WalkForwardEngine,
)
from trading_bot.domain import Candle, Signal, SignalAction


def candles(count: int) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result: list[Candle] = []
    for index in range(count):
        opened = start + timedelta(minutes=index)
        result.append(
            Candle(
                symbol="BTCUSDT",
                interval="1m",
                open_time=opened,
                close_time=opened + timedelta(seconds=59),
                open=Decimal(10),
                high=Decimal("10.5"),
                low=Decimal("9.5"),
                close=Decimal(10),
                volume=Decimal(10),
            )
        )
    return result


class AlwaysBuyStrategy:
    name = "ALWAYS_BUY"

    def generate_signal(self, history: Sequence[Candle]) -> Signal:
        latest = history[-1]
        return Signal(
            symbol=latest.symbol,
            interval=latest.interval,
            action=SignalAction.BUY,
            generated_at=latest.close_time,
            price=latest.close,
            stop_loss=Decimal(9),
            take_profit=Decimal(12),
            strategy=self.name,
            reason="Sinal determinístico.",
        )


def test_walk_forward_factory_sees_only_training_window() -> None:
    series = candles(8)
    observed_windows: list[tuple[datetime, datetime]] = []

    def factory(train: Sequence[Candle]) -> AlwaysBuyStrategy:
        observed_windows.append((train[0].open_time, train[-1].open_time))
        return AlwaysBuyStrategy()

    result = WalkForwardEngine(
        factory,
        config=WalkForwardConfig(
            train_size=4,
            test_size=2,
            step_size=2,
            warmup_size=2,
        ),
        backtest_config=BacktestConfig(
            fee_rate=Decimal(0),
            slippage_rate=Decimal(0),
            strategy_history_limit=10,
        ),
    ).run(series)

    assert len(result.folds) == 2
    assert observed_windows == [
        (series[0].open_time, series[3].open_time),
        (series[2].open_time, series[5].open_time),
    ]
    assert result.folds[0].result.trades[0].opened_at == series[4].open_time
    assert all(
        trade.opened_at >= series[fold.test_start_index].open_time
        for fold in result.folds
        for trade in fold.result.trades
    )


def test_walk_forward_ignores_incomplete_final_fold() -> None:
    result = WalkForwardEngine(
        lambda _: AlwaysBuyStrategy(),
        config=WalkForwardConfig(train_size=4, test_size=3),
    ).run(candles(9))

    assert len(result.folds) == 1
