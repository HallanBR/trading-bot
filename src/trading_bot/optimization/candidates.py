"""Grade pequena e explícita para a primeira pesquisa em candles de 5m."""

from decimal import Decimal
from functools import partial

from trading_bot.optimization.models import StrategyCandidate
from trading_bot.strategies import EmaRsiAtrConfig, EmaRsiAtrStrategy


def ema_rsi_atr_candidates() -> tuple[StrategyCandidate, ...]:
    """Retorna doze hipóteses; não gera combinações ilimitadas."""

    ema_pairs = (
        (5, 21),
        (9, 21),
        (9, 34),
        (12, 26),
        (12, 50),
        (20, 50),
    )
    exits = (
        (Decimal(1), Decimal(2)),
        (Decimal("1.5"), Decimal(3)),
    )
    candidates: list[StrategyCandidate] = []
    for fast_period, slow_period in ema_pairs:
        for stop_multiple, take_multiple in exits:
            config = EmaRsiAtrConfig(
                fast_ema_period=fast_period,
                slow_ema_period=slow_period,
                stop_atr_multiple=stop_multiple,
                take_atr_multiple=take_multiple,
            )
            name = (
                f"ema-{fast_period}-{slow_period}_atr-{stop_multiple}-{take_multiple}"
            )
            candidates.append(
                StrategyCandidate(
                    name=name,
                    build=partial(EmaRsiAtrStrategy, config),
                )
            )
    return tuple(candidates)
