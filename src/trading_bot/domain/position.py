"""Posição simulada atualmente aberta."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_bot.domain._validation import (
    require_aware_datetime,
    require_positive,
)
from trading_bot.domain.enums import PositionSide
from trading_bot.domain.signal import Signal


@dataclass(frozen=True, slots=True)
class Position:
    """Estado necessário para acompanhar uma operação ainda aberta."""

    position_id: str
    symbol: str
    interval: str
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    opened_at: datetime
    strategy: str
    entry_signal: Signal | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.opened_at, "opened_at")
        for field_name in ("quantity", "entry_price", "stop_loss", "take_profit"):
            require_positive(getattr(self, field_name), field_name)
        if (
            not self.position_id
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
            raise ValueError("O sinal de entrada não pertence à posição.")
