"""Configuração financeira do motor de backtest."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Capital e custos usados durante uma simulação histórica."""

    initial_equity: Decimal = Decimal(10000)
    fee_rate: Decimal = Decimal("0.001")
    slippage_rate: Decimal = Decimal("0.0005")

    def __post_init__(self) -> None:
        if self.initial_equity <= 0:
            raise ValueError("initial_equity deve ser positivo.")
        for name, value in {
            "fee_rate": self.fee_rate,
            "slippage_rate": self.slippage_rate,
        }.items():
            if not Decimal(0) <= value < Decimal(1):
                raise ValueError(f"{name} deve estar entre zero e um.")
