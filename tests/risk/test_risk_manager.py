"""Testes das regras centralizadas de gestão de risco."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from trading_bot.domain import Signal, SignalAction
from trading_bot.risk import RiskConfig, RiskContext, RiskManager


def signal(
    *,
    action: SignalAction = SignalAction.BUY,
    take_profit: Decimal = Decimal(110),
) -> Signal:
    common = {
        "symbol": "BTCUSDT",
        "interval": "5m",
        "action": action,
        "generated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "price": Decimal(100),
        "strategy": "TEST",
        "reason": "Entrada de teste.",
    }
    if action is SignalAction.HOLD:
        return Signal(**common)
    return Signal(
        **common,
        stop_loss=Decimal(95),
        take_profit=take_profit,
    )


def context(**overrides: object) -> RiskContext:
    values: dict[str, object] = {
        "account_equity": Decimal(10_000),
        "day_start_equity": Decimal(10_000),
        "daily_net_pnl": Decimal(0),
        "trades_today": 0,
        "consecutive_losses": 0,
        "open_positions": 0,
    }
    values.update(overrides)
    return RiskContext(**values)  # type: ignore[arg-type]


def test_manager_approves_signal_and_sizes_position() -> None:
    assessment = RiskManager().evaluate(signal(), context())

    assert assessment.approved is True
    assert assessment.quantity == Decimal(20)
    assert assessment.risk_amount == Decimal(100)
    assert assessment.notional == Decimal(2_000)
    assert assessment.risk_reward_ratio == Decimal(2)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"daily_net_pnl": Decimal(-300)}, "perda diária"),
        ({"trades_today": 5}, "operações"),
        ({"consecutive_losses": 3}, "perdas consecutivas"),
        ({"open_positions": 1}, "posições simultâneas"),
    ],
)
def test_manager_blocks_global_risk_limits(
    overrides: dict[str, object],
    message: str,
) -> None:
    assessment = RiskManager().evaluate(signal(), context(**overrides))

    assert assessment.approved is False
    assert message in assessment.reason
    assert assessment.quantity == 0


def test_manager_rejects_hold_signal() -> None:
    assessment = RiskManager().evaluate(
        signal(action=SignalAction.HOLD),
        context(),
    )

    assert assessment.approved is False
    assert "HOLD" in assessment.reason


def test_manager_rejects_low_risk_reward() -> None:
    manager = RiskManager(RiskConfig(min_risk_reward=Decimal("1.5")))

    assessment = manager.evaluate(
        signal(take_profit=Decimal(105)),
        context(),
    )

    assert assessment.approved is False
    assert "risco/retorno" in assessment.reason
