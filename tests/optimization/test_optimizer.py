"""Testes do otimizador que pode rejeitar todos os candidatos."""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_bot.backtest import BacktestConfig
from trading_bot.domain import Candle, Signal, SignalAction
from trading_bot.optimization import (
    ControlledOptimizer,
    OptimizationConfig,
    StrategyCandidate,
)


def candles() -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result: list[Candle] = []
    for index in range(4):
        opened = start + timedelta(minutes=5 * index)
        result.append(
            Candle(
                symbol="BTCUSDT",
                interval="5m",
                open_time=opened,
                close_time=opened + timedelta(minutes=5) - timedelta(milliseconds=1),
                open=Decimal(10),
                high=Decimal(12),
                low=Decimal("9.5"),
                close=Decimal(10),
                volume=Decimal(10),
            )
        )
    return result


class OneShotStrategy:
    def __init__(self, action: SignalAction) -> None:
        self.action = action
        self.name = f"ONE_SHOT_{action.value}"

    def generate_signal(self, history: Sequence[Candle]) -> Signal:
        latest = history[-1]
        if len(history) == 2:
            return Signal(
                symbol=latest.symbol,
                interval=latest.interval,
                action=self.action,
                generated_at=latest.close_time,
                price=latest.close,
                stop_loss=(
                    Decimal(9) if self.action is SignalAction.BUY else Decimal(11)
                ),
                take_profit=(
                    Decimal(12) if self.action is SignalAction.BUY else Decimal(8)
                ),
                strategy=self.name,
                reason="Sinal determinístico.",
            )
        return Signal(
            symbol=latest.symbol,
            interval=latest.interval,
            action=SignalAction.HOLD,
            generated_at=latest.close_time,
            price=latest.close,
            strategy=self.name,
            reason="Entrada já avaliada.",
        )


def optimizer(
    candidates: tuple[StrategyCandidate, ...],
) -> ControlledOptimizer:
    return ControlledOptimizer(
        candidates,
        config=OptimizationConfig(
            validation_size=2,
            warmup_size=2,
            minimum_trades=1,
            minimum_profit_factor=Decimal(1),
            maximum_drawdown_percent=Decimal(100),
            maximum_candidates=4,
        ),
        backtest_config=BacktestConfig(
            fee_rate=Decimal(0),
            slippage_rate=Decimal(0),
            strategy_history_limit=10,
        ),
    )


def test_optimizer_selects_profitable_candidate() -> None:
    candidates = (
        StrategyCandidate(
            "winning",
            lambda: OneShotStrategy(SignalAction.BUY),
        ),
        StrategyCandidate(
            "losing",
            lambda: OneShotStrategy(SignalAction.SELL),
        ),
    )

    result = optimizer(candidates).optimize(candles())

    assert result.best_trial is not None
    assert result.best_trial.candidate.name == "winning"
    assert result.best_trial.result.net_profit > 0
    assert result.validation_start_index == 2


def test_optimizer_returns_none_when_every_candidate_fails() -> None:
    candidates = (
        StrategyCandidate(
            "losing",
            lambda: OneShotStrategy(SignalAction.SELL),
        ),
    )

    result = optimizer(candidates).optimize(candles())

    assert result.best_trial is None
    assert result.trials[0].eligible is False
    assert result.trials[0].rejection_reason == "Lucro líquido não positivo."


def test_optimizer_rejects_insufficient_training_history() -> None:
    candidates = (
        StrategyCandidate(
            "winning",
            lambda: OneShotStrategy(SignalAction.BUY),
        ),
    )

    with pytest.raises(ValueError, match="Treino insuficiente"):
        optimizer(candidates).optimize(candles()[:3])
