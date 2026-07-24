"""Testes da orquestração incremental do paper trading."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from trading_bot.domain import Candle, Signal, SignalAction, Trade
from trading_bot.execution import FillSimulator, PaperExecutor
from trading_bot.learning import LearningDatabase, LosingTradeRepository
from trading_bot.notifications import NotificationService
from trading_bot.risk import RiskConfig, RiskManager
from trading_bot.trading import PaperTradingEngine


@dataclass
class RecordingNotifier:
    name: str = "recording"
    calls: int = 0

    def notify_trade(self, trade: Trade) -> None:
        del trade
        self.calls += 1


class SignalAtTenStrategy:
    name = "SIGNAL_AT_TEN"

    def __init__(self) -> None:
        self.calls = 0

    def generate_signal(self, candles: Sequence[Candle]) -> Signal:
        self.calls += 1
        latest = candles[-1]
        if latest.close == Decimal(10):
            return Signal(
                symbol=latest.symbol,
                interval=latest.interval,
                action=SignalAction.BUY,
                generated_at=latest.close_time,
                price=latest.close,
                stop_loss=Decimal(9),
                take_profit=Decimal(12),
                strategy=self.name,
                reason="Entrada após aquecimento.",
            )
        return Signal(
            symbol=latest.symbol,
            interval=latest.interval,
            action=SignalAction.HOLD,
            generated_at=latest.close_time,
            price=latest.close,
            strategy=self.name,
            reason="Sem entrada.",
        )


def candle(
    index: int,
    *,
    open_price: str,
    high: str,
    low: str,
    close: str,
) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index)
    return Candle(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=open_time + timedelta(seconds=59),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(10),
    )


def paper_executor() -> PaperExecutor:
    risk = RiskManager(
        RiskConfig(
            risk_per_trade=Decimal("0.10"),
            max_daily_loss=Decimal("0.50"),
            max_position_fraction=Decimal(1),
            min_risk_reward=Decimal(1),
            max_trades_per_day=10,
            max_consecutive_losses=10,
            max_open_positions=1,
        )
    )
    return PaperExecutor(
        initial_equity=Decimal(1_000),
        risk_manager=risk,
        fills=FillSimulator(fee_rate=Decimal(0), slippage_rate=Decimal(0)),
    )


def test_first_batch_only_primes_history_without_retroactive_trade() -> None:
    strategy = SignalAtTenStrategy()
    engine = PaperTradingEngine(strategy, paper_executor())
    history = [
        candle(0, open_price="9", high="9.5", low="8.5", close="9"),
        candle(1, open_price="9", high="10", low="8.5", close="10"),
    ]

    update = engine.process_candles(history)

    assert update.primed_candles == 2
    assert update.processed_candles == 0
    assert update.closed_trades == ()
    assert strategy.calls == 0


def test_new_candles_generate_trade_and_one_notification() -> None:
    strategy = SignalAtTenStrategy()
    notifier = RecordingNotifier()
    engine = PaperTradingEngine(
        strategy,
        paper_executor(),
        notifications=NotificationService([notifier]),
    )
    warmup = candle(0, open_price="9", high="9.5", low="8.5", close="9")
    signal_candle = candle(1, open_price="9", high="10", low="8.5", close="10")
    exit_candle = candle(2, open_price="10", high="12", low="9.5", close="11")
    engine.process_candles([warmup])

    first_update = engine.process_candles([signal_candle])
    second_update = engine.process_candles([exit_candle])
    duplicate_update = engine.process_candles([exit_candle])

    assert first_update.closed_trades == ()
    assert second_update.processed_candles == 1
    assert len(second_update.closed_trades) == 1
    assert second_update.notifications[0].success is True
    assert notifier.calls == 1
    assert duplicate_update.processed_candles == 0
    assert notifier.calls == 1


def test_losing_trade_is_written_to_separate_learning_database(
    tmp_path: Path,
) -> None:
    database = LearningDatabase.from_path(tmp_path / "losses.db")
    database.create_schema()
    losses = LosingTradeRepository(database)
    engine = PaperTradingEngine(
        SignalAtTenStrategy(),
        paper_executor(),
        losing_trades=losses,
    )
    warmup = candle(0, open_price="9", high="9.5", low="8.5", close="9")
    signal_candle = candle(1, open_price="9", high="10", low="8.5", close="10")
    loss_candle = candle(2, open_price="10", high="10.5", low="9", close="9.5")
    engine.process_candles([warmup])

    engine.process_candles([signal_candle])
    update = engine.process_candles([loss_candle])

    assert len(update.closed_trades) == 1
    assert update.recorded_losses == 1
    assert losses.count() == 1
    database.dispose()
