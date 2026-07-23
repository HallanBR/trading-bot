"""Entidades centrais do domínio."""

from trading_bot.domain.candle import Candle
from trading_bot.domain.enums import (
    ExitReason,
    PositionSide,
    SignalAction,
    TradeResult,
)
from trading_bot.domain.position import Position
from trading_bot.domain.signal import Signal
from trading_bot.domain.trade import Trade

__all__ = [
    "Candle",
    "ExitReason",
    "Position",
    "PositionSide",
    "Signal",
    "SignalAction",
    "Trade",
    "TradeResult",
]
