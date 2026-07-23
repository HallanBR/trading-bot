"""Resultado imutável de uma execução do backtest."""

from dataclasses import dataclass
from decimal import Decimal

from trading_bot.backtest.metrics import max_drawdown_percent, profit_factor
from trading_bot.domain import Trade, TradeResult


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Trades, curva de capital e métricas principais da simulação."""

    initial_equity: Decimal
    final_equity: Decimal
    trades: tuple[Trade, ...]
    equity_curve: tuple[Decimal, ...]
    rejected_signals: int = 0

    def __post_init__(self) -> None:
        if self.initial_equity <= 0 or self.final_equity <= 0:
            raise ValueError("O capital do backtest deve ser positivo.")
        if self.rejected_signals < 0:
            raise ValueError("rejected_signals não pode ser negativo.")
        if not self.equity_curve or self.equity_curve[0] != self.initial_equity:
            raise ValueError("A curva de capital deve começar no capital inicial.")
        if self.equity_curve[-1] != self.final_equity:
            raise ValueError("A curva de capital deve terminar no capital final.")

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(trade.result is TradeResult.WIN for trade in self.trades)

    @property
    def losses(self) -> int:
        return sum(trade.result is TradeResult.LOSS for trade in self.trades)

    @property
    def net_profit(self) -> Decimal:
        return self.final_equity - self.initial_equity

    @property
    def return_percent(self) -> Decimal:
        return (self.net_profit / self.initial_equity) * Decimal(100)

    @property
    def win_rate_percent(self) -> Decimal:
        if not self.trades:
            return Decimal(0)
        return (Decimal(self.wins) / Decimal(self.total_trades)) * Decimal(100)

    @property
    def max_drawdown_percent(self) -> Decimal:
        return max_drawdown_percent(self.equity_curve)

    @property
    def profit_factor(self) -> Decimal | None:
        return profit_factor(self.trades)
