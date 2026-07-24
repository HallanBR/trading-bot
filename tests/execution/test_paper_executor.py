"""Testes da conta e execução virtual stateful."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trading_bot.domain import Candle, Signal, SignalAction, TradeResult
from trading_bot.execution import FillSimulator, PaperExecutor
from trading_bot.risk import RiskConfig, RiskManager


def executor(*, min_risk_reward: str = "1") -> PaperExecutor:
    risk = RiskManager(
        RiskConfig(
            risk_per_trade=Decimal("0.10"),
            max_daily_loss=Decimal("0.50"),
            max_position_fraction=Decimal(1),
            min_risk_reward=Decimal(min_risk_reward),
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


def buy_signal(*, target: str = "12") -> Signal:
    return Signal(
        symbol="BTCUSDT",
        interval="1m",
        action=SignalAction.BUY,
        generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        price=Decimal(10),
        stop_loss=Decimal(9),
        take_profit=Decimal(target),
        strategy="TEST",
        reason="Entrada virtual de teste.",
        indicators={"rsi": Decimal(55)},
    )


def market_candle(
    *,
    high: str,
    low: str,
    close: str = "11",
) -> Candle:
    open_time = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    return Candle(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=open_time + timedelta(seconds=59),
        open=Decimal(10),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(10),
    )


def test_paper_executor_opens_and_closes_virtual_trade() -> None:
    paper = executor()

    assert paper.queue_signal(buy_signal()) is True
    trades = paper.process_candle(market_candle(high="12", low="9.5"))

    assert len(trades) == 1
    assert trades[0].result is TradeResult.WIN
    assert trades[0].trade_id == "paper-trade-1"
    assert trades[0].entry_signal is not None
    assert trades[0].entry_signal.indicators["rsi"] == Decimal(55)
    assert paper.snapshot().equity == Decimal(1_200)
    assert paper.snapshot().open_position is None


def test_paper_executor_records_risk_rejection() -> None:
    paper = executor(min_risk_reward="1")
    paper.queue_signal(buy_signal(target="10.5"))

    trades = paper.process_candle(market_candle(high="11", low="9.5"))

    assert trades == ()
    assert paper.snapshot().rejected_signals == 1
    assert paper.snapshot().equity == Decimal(1_000)


def test_paper_executor_does_not_replace_pending_signal() -> None:
    paper = executor()

    assert paper.queue_signal(buy_signal()) is True
    assert paper.queue_signal(buy_signal()) is False
    assert paper.snapshot().has_pending_signal is True
