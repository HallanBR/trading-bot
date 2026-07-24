"""Construções compartilhadas por estratégias, sem executar ordens."""

from collections.abc import Mapping, Sequence
from decimal import Decimal

from trading_bot.domain import Candle, Signal, SignalAction


def validate_candle_series(candles: Sequence[Candle]) -> None:
    if not candles:
        raise ValueError("Ao menos um candle é necessário.")
    first = candles[0]
    previous_time = first.open_time
    for candle in candles:
        if candle.symbol != first.symbol or candle.interval != first.interval:
            raise ValueError("Todos os candles devem pertencer à mesma série.")
    for candle in candles[1:]:
        if candle.open_time <= previous_time:
            raise ValueError("Candles devem estar em ordem cronológica.")
        previous_time = candle.open_time


def hold_signal(
    candle: Candle,
    *,
    strategy: str,
    reason: str,
    indicators: Mapping[str, Decimal | None],
) -> Signal:
    return Signal(
        symbol=candle.symbol,
        interval=candle.interval,
        action=SignalAction.HOLD,
        generated_at=candle.close_time,
        price=candle.close,
        strategy=strategy,
        reason=reason,
        indicators=indicators,
    )


def atr_entry_signal(
    candle: Candle,
    *,
    action: SignalAction,
    current_atr: Decimal,
    stop_atr_multiple: Decimal,
    take_atr_multiple: Decimal,
    strategy: str,
    reason: str,
    indicators: Mapping[str, Decimal | None],
) -> Signal:
    stop_distance = current_atr * stop_atr_multiple
    target_distance = current_atr * take_atr_multiple
    if action is SignalAction.BUY:
        stop_loss = candle.close - stop_distance
        take_profit = candle.close + target_distance
    elif action is SignalAction.SELL:
        stop_loss = candle.close + stop_distance
        take_profit = candle.close - target_distance
    else:
        raise ValueError("Uma entrada exige BUY ou SELL.")

    if stop_loss <= 0 or take_profit <= 0:
        return hold_signal(
            candle,
            strategy=strategy,
            reason="ATR gerou níveis de preço inválidos.",
            indicators=indicators,
        )
    return Signal(
        symbol=candle.symbol,
        interval=candle.interval,
        action=action,
        generated_at=candle.close_time,
        price=candle.close,
        stop_loss=stop_loss,
        take_profit=take_profit,
        strategy=strategy,
        reason=reason,
        indicators=indicators,
    )


def target_covers_costs(
    *,
    price: Decimal,
    current_atr: Decimal,
    take_atr_multiple: Decimal,
    projected_round_trip_cost_rate: Decimal,
    minimum_multiple: Decimal,
) -> bool:
    target_rate = (current_atr * take_atr_multiple) / price
    required_rate = projected_round_trip_cost_rate * minimum_multiple
    return target_rate >= required_rate
