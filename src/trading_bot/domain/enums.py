"""Enumerações usadas durante o ciclo de uma operação."""

from enum import Enum


class SignalAction(str, Enum):
    """Decisão produzida por uma estratégia."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class PositionSide(str, Enum):
    """Direção de uma posição aberta."""

    LONG = "LONG"
    SHORT = "SHORT"


class ExitReason(str, Enum):
    """Motivo do encerramento de uma posição."""

    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    STRATEGY = "STRATEGY"
    MANUAL = "MANUAL"
    END_OF_DATA = "END_OF_DATA"


class TradeResult(str, Enum):
    """Classificação do resultado líquido de uma operação."""

    WIN = "WIN"
    LOSS = "LOSS"
    BREAK_EVEN = "BREAK_EVEN"
