"""Dimensionamento de posição por risco financeiro."""

from dataclasses import dataclass
from decimal import Decimal

from trading_bot.domain import Signal, SignalAction


@dataclass(frozen=True, slots=True)
class PositionSize:
    """Quantidade calculada e sua exposição financeira."""

    quantity: Decimal
    risk_amount: Decimal
    notional: Decimal


def calculate_position_size(
    signal: Signal,
    *,
    account_equity: Decimal,
    risk_fraction: Decimal,
    max_position_fraction: Decimal,
    max_position_notional: Decimal | None = None,
) -> PositionSize:
    """Limita a posição pelo risco no stop e pelo valor nocional máximo."""

    if signal.action is SignalAction.HOLD:
        raise ValueError("Não é possível dimensionar um sinal HOLD.")
    if signal.stop_loss is None:
        raise ValueError("O sinal deve possuir stop-loss.")
    if account_equity <= 0:
        raise ValueError("account_equity deve ser positivo.")
    if not Decimal(0) < risk_fraction <= Decimal(1):
        raise ValueError("risk_fraction deve estar entre zero e um.")
    if not Decimal(0) < max_position_fraction <= Decimal(1):
        raise ValueError("max_position_fraction deve estar entre zero e um.")
    if max_position_notional is not None and max_position_notional <= 0:
        raise ValueError("max_position_notional deve ser positivo.")

    stop_distance = abs(signal.price - signal.stop_loss)
    if stop_distance == 0:
        raise ValueError("A distância até o stop deve ser positiva.")

    risk_budget = account_equity * risk_fraction
    risk_limited_quantity = risk_budget / stop_distance
    max_notional = account_equity * max_position_fraction
    if max_position_notional is not None:
        max_notional = min(max_notional, max_position_notional)
    notional_limited_quantity = max_notional / signal.price
    quantity = min(risk_limited_quantity, notional_limited_quantity)

    return PositionSize(
        quantity=quantity,
        risk_amount=quantity * stop_distance,
        notional=quantity * signal.price,
    )
