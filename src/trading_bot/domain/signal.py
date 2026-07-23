"""Sinal produzido por uma estratégia."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from trading_bot.domain._validation import (
    require_aware_datetime,
    require_positive,
)
from trading_bot.domain.enums import SignalAction


@dataclass(frozen=True, slots=True)
class Signal:
    """Decisão explicável, sem capacidade de executar ordens."""

    symbol: str
    interval: str
    action: SignalAction
    generated_at: datetime
    price: Decimal
    strategy: str
    reason: str
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    indicators: Mapping[str, Decimal | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_aware_datetime(self.generated_at, "generated_at")
        require_positive(self.price, "price")
        if not self.symbol or not self.interval or not self.strategy or not self.reason:
            raise ValueError(
                "Símbolo, intervalo, estratégia e motivo são obrigatórios."
            )

        if self.action is SignalAction.HOLD:
            if self.stop_loss is not None or self.take_profit is not None:
                raise ValueError("Sinais HOLD não podem definir stop ou alvo.")
        else:
            if self.stop_loss is None or self.take_profit is None:
                raise ValueError("Sinais BUY e SELL devem definir stop e alvo.")
            require_positive(self.stop_loss, "stop_loss")
            require_positive(self.take_profit, "take_profit")
            self._validate_price_levels()

        object.__setattr__(
            self,
            "indicators",
            MappingProxyType(dict(self.indicators)),
        )

    def _validate_price_levels(self) -> None:
        assert self.stop_loss is not None
        assert self.take_profit is not None

        if self.action is SignalAction.BUY:
            valid = self.stop_loss < self.price < self.take_profit
        else:
            valid = self.take_profit < self.price < self.stop_loss
        if not valid:
            raise ValueError("Stop, entrada e alvo estão em ordem inválida.")
