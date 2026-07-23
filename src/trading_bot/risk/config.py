"""Configuração dos limites de risco."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Limites conservadores e configuráveis usados antes de cada entrada."""

    risk_per_trade: Decimal = Decimal("0.01")
    max_daily_loss: Decimal = Decimal("0.03")
    max_position_fraction: Decimal = Decimal("0.25")
    min_risk_reward: Decimal = Decimal("1.5")
    max_trades_per_day: int = 5
    max_consecutive_losses: int = 3
    max_open_positions: int = 1

    def __post_init__(self) -> None:
        fractions = {
            "risk_per_trade": self.risk_per_trade,
            "max_daily_loss": self.max_daily_loss,
            "max_position_fraction": self.max_position_fraction,
        }
        for name, fraction_value in fractions.items():
            if not Decimal(0) < fraction_value <= Decimal(1):
                raise ValueError(f"{name} deve estar entre zero e um.")
        if self.min_risk_reward <= 0:
            raise ValueError("min_risk_reward deve ser positivo.")

        limits = {
            "max_trades_per_day": self.max_trades_per_day,
            "max_consecutive_losses": self.max_consecutive_losses,
            "max_open_positions": self.max_open_positions,
        }
        for name, limit_value in limits.items():
            if (
                isinstance(limit_value, bool)
                or not isinstance(limit_value, int)
                or limit_value <= 0
            ):
                raise ValueError(f"{name} deve ser um inteiro positivo.")
