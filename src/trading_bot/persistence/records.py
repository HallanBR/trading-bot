"""Objetos de leitura retornados pelos repositórios."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    """Resumo persistido de uma execução de backtest."""

    run_id: str
    created_at: datetime
    strategy: str
    symbol: str
    interval: str
    initial_equity: Decimal
    final_equity: Decimal
    net_profit: Decimal
    return_percent: Decimal
    win_rate_percent: Decimal
    max_drawdown_percent: Decimal
    profit_factor: Decimal | None
    total_trades: int
    wins: int
    losses: int
    rejected_signals: int
