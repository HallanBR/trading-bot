"""Resultado da avaliação de risco de um sinal."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Aprovação ou rejeição explicável antes de criar uma posição."""

    approved: bool
    reason: str
    quantity: Decimal = Decimal(0)
    risk_amount: Decimal = Decimal(0)
    notional: Decimal = Decimal(0)
    risk_reward_ratio: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        values = (
            self.quantity,
            self.risk_amount,
            self.notional,
            self.risk_reward_ratio,
        )
        if not self.reason:
            raise ValueError("A avaliação deve informar um motivo.")
        if any(value < 0 for value in values):
            raise ValueError("Valores da avaliação não podem ser negativos.")
        if self.approved and any(value <= 0 for value in values):
            raise ValueError("Uma aprovação deve possuir valores positivos.")
        if not self.approved and any(value != 0 for value in values):
            raise ValueError("Uma rejeição não pode dimensionar posição.")
