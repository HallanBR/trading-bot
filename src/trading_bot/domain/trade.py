"""Registro imutável de uma operação encerrada."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_bot.domain._validation import (
    require_aware_datetime,
    require_non_negative,
    require_positive,
)
from trading_bot.domain.enums import ExitReason, PositionSide, TradeResult
from trading_bot.domain.signal import Signal


@dataclass(frozen=True, slots=True)
class Trade:
    """Operação finalizada com cálculo de resultado bruto e líquido."""

    trade_id: str
    symbol: str
    interval: str
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    fees: Decimal
    opened_at: datetime
    closed_at: datetime
    strategy: str
    exit_reason: ExitReason
    entry_signal: Signal | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.opened_at, "opened_at")
        require_aware_datetime(self.closed_at, "closed_at")
        for field_name in (
            "quantity",
            "entry_price",
            "exit_price",
            "stop_loss",
            "take_profit",
        ):
            require_positive(getattr(self, field_name), field_name)
        require_non_negative(self.fees, "fees")
        if self.closed_at < self.opened_at:
            raise ValueError("closed_at não pode ser anterior a opened_at.")
        if (
            not self.trade_id
            or not self.symbol
            or not self.interval
            or not self.strategy
        ):
            raise ValueError("Identificadores e estratégia são obrigatórios.")
        if self.side is PositionSide.LONG:
            valid = self.stop_loss < self.entry_price < self.take_profit
        else:
            valid = self.take_profit < self.entry_price < self.stop_loss
        if not valid:
            raise ValueError("Stop, entrada e alvo estão em ordem inválida.")
        if self.entry_signal is not None and (
            self.entry_signal.symbol != self.symbol
            or self.entry_signal.interval != self.interval
            or self.entry_signal.strategy != self.strategy
        ):
            raise ValueError("O sinal de entrada não pertence ao trade.")

    @property
    def gross_pnl(self) -> Decimal:
        price_change = self.exit_price - self.entry_price
        if self.side is PositionSide.SHORT:
            price_change = -price_change
        return price_change * self.quantity

    @property
    def net_pnl(self) -> Decimal:
        return self.gross_pnl - self.fees

    @property
    def result(self) -> TradeResult:
        if self.net_pnl > 0:
            return TradeResult.WIN
        if self.net_pnl < 0:
            return TradeResult.LOSS
        return TradeResult.BREAK_EVEN
