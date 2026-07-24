"""Objetos imutáveis retornados pelo banco de aprendizado."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_bot.domain import ExitReason, PositionSide


@dataclass(frozen=True, slots=True)
class LosingTradeCase:
    """Exemplo perdedor pronto para análise e treinamento futuro."""

    case_id: str
    recorded_at: datetime
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
    gross_pnl: Decimal
    net_pnl: Decimal
    opened_at: datetime
    closed_at: datetime
    strategy: str
    exit_reason: ExitReason
    signal_generated_at: datetime | None
    signal_price: Decimal | None
    signal_reason: str | None
    indicators: Mapping[str, Decimal | None]
