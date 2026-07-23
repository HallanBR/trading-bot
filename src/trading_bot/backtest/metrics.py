"""Cálculos de desempenho derivados dos trades e da curva de capital."""

from collections.abc import Sequence
from decimal import Decimal

from trading_bot.domain import Trade


def max_drawdown_percent(equity_curve: Sequence[Decimal]) -> Decimal:
    """Retorna a maior queda percentual a partir de um pico anterior."""

    if not equity_curve:
        return Decimal(0)

    peak = equity_curve[0]
    maximum = Decimal(0)
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            drawdown = ((peak - equity) / peak) * Decimal(100)
            maximum = max(maximum, drawdown)
    return maximum


def profit_factor(trades: Sequence[Trade]) -> Decimal | None:
    """Divide lucros líquidos pelas perdas líquidas absolutas."""

    gross_profit = sum(
        (trade.net_pnl for trade in trades if trade.net_pnl > 0),
        start=Decimal(0),
    )
    gross_loss = abs(
        sum(
            (trade.net_pnl for trade in trades if trade.net_pnl < 0),
            start=Decimal(0),
        )
    )
    if gross_loss == 0:
        return None
    return gross_profit / gross_loss
