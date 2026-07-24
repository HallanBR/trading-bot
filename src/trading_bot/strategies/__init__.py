"""Contratos e estratégias isoladas."""

from trading_bot.strategies.base import Strategy
from trading_bot.strategies.breakout import BreakoutConfig, BreakoutVolumeStrategy
from trading_bot.strategies.ema_rsi_atr import (
    EmaRsiAtrConfig,
    EmaRsiAtrStrategy,
)
from trading_bot.strategies.filtered_trend import (
    FilteredTrendConfig,
    FilteredTrendStrategy,
)
from trading_bot.strategies.mean_reversion import (
    MeanReversionConfig,
    MeanReversionStrategy,
)
from trading_bot.strategies.registry import STRATEGY_BUILDERS, create_strategy

__all__ = [
    "STRATEGY_BUILDERS",
    "BreakoutConfig",
    "BreakoutVolumeStrategy",
    "EmaRsiAtrConfig",
    "EmaRsiAtrStrategy",
    "FilteredTrendConfig",
    "FilteredTrendStrategy",
    "MeanReversionConfig",
    "MeanReversionStrategy",
    "Strategy",
    "create_strategy",
]
