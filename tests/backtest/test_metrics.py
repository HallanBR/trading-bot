"""Testes das métricas de backtest."""

from decimal import Decimal

from trading_bot.backtest.metrics import max_drawdown_percent


def test_max_drawdown_uses_previous_equity_peak() -> None:
    curve = [
        Decimal(100),
        Decimal(120),
        Decimal(90),
        Decimal(110),
        Decimal(80),
    ]

    assert max_drawdown_percent(curve) == Decimal("33.33333333333333333333333333")


def test_max_drawdown_is_zero_for_rising_curve() -> None:
    assert max_drawdown_percent([Decimal(100), Decimal(110)]) == 0
