"""Registro explícito das estratégias disponíveis para pesquisa e paper."""

from collections.abc import Callable

from trading_bot.strategies.base import Strategy
from trading_bot.strategies.breakout import BreakoutVolumeStrategy
from trading_bot.strategies.ema_rsi_atr import EmaRsiAtrStrategy
from trading_bot.strategies.filtered_trend import FilteredTrendStrategy
from trading_bot.strategies.mean_reversion import MeanReversionStrategy

StrategyBuilder = Callable[[], Strategy]

STRATEGY_BUILDERS: dict[str, StrategyBuilder] = {
    "base": EmaRsiAtrStrategy,
    "filtered": FilteredTrendStrategy,
    "breakout": BreakoutVolumeStrategy,
    "mean-reversion": MeanReversionStrategy,
}


def create_strategy(name: str) -> Strategy:
    """Cria uma estratégia pelo nome estável usado na linha de comando."""

    normalized = name.strip().lower()
    try:
        builder = STRATEGY_BUILDERS[normalized]
    except KeyError as exc:
        allowed = ", ".join(STRATEGY_BUILDERS)
        raise ValueError(f"Estratégia inválida. Opções: {allowed}.") from exc
    return builder()
