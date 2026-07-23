"""Testes do motor cronológico de backtest."""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trading_bot.backtest import BacktestConfig, BacktestEngine
from trading_bot.domain import (
    Candle,
    ExitReason,
    Signal,
    SignalAction,
    TradeResult,
)
from trading_bot.risk import RiskConfig, RiskManager


class OneShotStrategy:
    """Gera uma única entrada no fechamento do primeiro candle."""

    name = "ONE_SHOT"

    def __init__(
        self,
        *,
        action: SignalAction = SignalAction.BUY,
        stop_loss: Decimal = Decimal(9),
        take_profit: Decimal = Decimal(12),
    ) -> None:
        self.action = action
        self.stop_loss = stop_loss
        self.take_profit = take_profit

    def generate_signal(self, candles: Sequence[Candle]) -> Signal:
        latest = candles[-1]
        if len(candles) == 1:
            return Signal(
                symbol=latest.symbol,
                interval=latest.interval,
                action=self.action,
                generated_at=latest.close_time,
                price=latest.close,
                stop_loss=self.stop_loss,
                take_profit=self.take_profit,
                strategy=self.name,
                reason="Sinal determinístico para teste.",
            )
        return Signal(
            symbol=latest.symbol,
            interval=latest.interval,
            action=SignalAction.HOLD,
            generated_at=latest.close_time,
            price=latest.close,
            strategy=self.name,
            reason="Entrada já emitida.",
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


def first_candle() -> Candle:
    return candle(0, open_price="10", high="10.5", low="9.5", close="10")


def engine(
    strategy: OneShotStrategy | None = None,
    *,
    fee_rate: str = "0",
    slippage_rate: str = "0",
    min_risk_reward: str = "1",
) -> BacktestEngine:
    risk_manager = RiskManager(
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
    return BacktestEngine(
        strategy or OneShotStrategy(),
        risk_manager=risk_manager,
        config=BacktestConfig(
            initial_equity=Decimal(1_000),
            fee_rate=Decimal(fee_rate),
            slippage_rate=Decimal(slippage_rate),
        ),
    )


def test_entry_occurs_only_on_next_candle_and_hits_target() -> None:
    entry_candle = candle(
        1,
        open_price="10",
        high="12",
        low="9.5",
        close="11",
    )

    result = engine().run([first_candle(), entry_candle])

    assert result.total_trades == 1
    trade = result.trades[0]
    assert trade.opened_at == entry_candle.open_time
    assert trade.exit_reason is ExitReason.TAKE_PROFIT
    assert trade.result is TradeResult.WIN
    assert trade.entry_price == Decimal(10)
    assert trade.exit_price == Decimal(12)
    assert result.final_equity == Decimal(1_200)


def test_stop_has_priority_if_stop_and_target_touch_same_candle() -> None:
    ambiguous_candle = candle(
        1,
        open_price="10",
        high="12",
        low="9",
        close="11",
    )

    result = engine().run([first_candle(), ambiguous_candle])

    trade = result.trades[0]
    assert trade.exit_reason is ExitReason.STOP_LOSS
    assert trade.result is TradeResult.LOSS
    assert trade.exit_price == Decimal(9)
    assert result.final_equity == Decimal(900)
    assert result.max_drawdown_percent == Decimal(10)


def test_short_position_profits_when_target_is_reached() -> None:
    strategy = OneShotStrategy(
        action=SignalAction.SELL,
        stop_loss=Decimal(11),
        take_profit=Decimal(8),
    )
    target_candle = candle(
        1,
        open_price="10",
        high="10.5",
        low="8",
        close="9",
    )

    result = engine(strategy).run([first_candle(), target_candle])

    trade = result.trades[0]
    assert trade.exit_reason is ExitReason.TAKE_PROFIT
    assert trade.result is TradeResult.WIN
    assert trade.side.value == "SHORT"
    assert result.final_equity == Decimal(1_200)


def test_open_position_is_closed_at_end_of_data() -> None:
    final_candle = candle(
        1,
        open_price="10",
        high="11",
        low="9.5",
        close="10.5",
    )

    result = engine().run([first_candle(), final_candle])

    trade = result.trades[0]
    assert trade.exit_reason is ExitReason.END_OF_DATA
    assert trade.exit_price == Decimal("10.5")
    assert result.final_equity == Decimal(1_050)


def test_fees_and_slippage_reduce_result() -> None:
    target_candle = candle(
        1,
        open_price="10",
        high="13",
        low="10",
        close="12",
    )

    result = engine(fee_rate="0.001", slippage_rate="0.001").run(
        [first_candle(), target_candle]
    )

    trade = result.trades[0]
    assert trade.entry_price > target_candle.open
    assert trade.exit_price < trade.take_profit
    assert trade.fees > 0
    assert trade.net_pnl < trade.gross_pnl


def test_risk_manager_can_reject_pending_signal() -> None:
    low_reward_strategy = OneShotStrategy(take_profit=Decimal("10.5"))
    second_candle = candle(
        1,
        open_price="10",
        high="10.5",
        low="9.5",
        close="10",
    )

    result = engine(
        low_reward_strategy,
        min_risk_reward="1",
    ).run([first_candle(), second_candle])

    assert result.total_trades == 0
    assert result.rejected_signals == 1
    assert result.final_equity == Decimal(1_000)


def test_empty_history_returns_unchanged_equity() -> None:
    result = engine().run([])

    assert result.total_trades == 0
    assert result.net_profit == 0
    assert result.equity_curve == (Decimal(1_000),)
