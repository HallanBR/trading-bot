"""Otimização controlada com rejeição de candidatos frágeis."""

from trading_bot.optimization.candidates import ema_rsi_atr_candidates
from trading_bot.optimization.fallback import NoTradeStrategy
from trading_bot.optimization.models import (
    OptimizationConfig,
    OptimizationResult,
    OptimizationTrial,
    StrategyCandidate,
)
from trading_bot.optimization.optimizer import ControlledOptimizer

__all__ = [
    "ControlledOptimizer",
    "NoTradeStrategy",
    "OptimizationConfig",
    "OptimizationResult",
    "OptimizationTrial",
    "StrategyCandidate",
    "ema_rsi_atr_candidates",
]
