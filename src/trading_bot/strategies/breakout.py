"""Estratégia candidata de rompimento com volume e tendência."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from trading_bot.domain import Candle, Signal, SignalAction
from trading_bot.indicators import atr, ema, relative_volume
from trading_bot.strategies._common import (
    atr_entry_signal,
    hold_signal,
    target_covers_costs,
    validate_candle_series,
)


@dataclass(frozen=True, slots=True)
class BreakoutConfig:
    range_period: int = 20
    trend_ema_period: int = 50
    volume_period: int = 20
    atr_period: int = 14
    minimum_relative_volume: Decimal = Decimal("1.25")
    stop_atr_multiple: Decimal = Decimal("1.5")
    take_atr_multiple: Decimal = Decimal(3)
    projected_round_trip_cost_rate: Decimal = Decimal("0.003")
    minimum_target_cost_multiple: Decimal = Decimal("1.25")

    def __post_init__(self) -> None:
        periods = (
            self.range_period,
            self.trend_ema_period,
            self.volume_period,
            self.atr_period,
        )
        if any(
            isinstance(period, bool) or not isinstance(period, int) or period <= 0
            for period in periods
        ):
            raise ValueError("Períodos devem ser inteiros positivos.")
        decimals = (
            self.minimum_relative_volume,
            self.stop_atr_multiple,
            self.take_atr_multiple,
            self.minimum_target_cost_multiple,
        )
        if any(value <= 0 for value in decimals):
            raise ValueError("Limites da estratégia devem ser positivos.")
        if not Decimal(0) <= self.projected_round_trip_cost_rate < Decimal(1):
            raise ValueError("Custo projetado deve estar entre zero e um.")


class BreakoutVolumeStrategy:
    """Opera fechamento fora da faixa quando tendência e volume confirmam."""

    name = "BREAKOUT_VOLUME_ATR"

    def __init__(self, config: BreakoutConfig | None = None) -> None:
        self.config = config or BreakoutConfig()

    def generate_signal(self, candles: Sequence[Candle]) -> Signal:
        validate_candle_series(candles)
        latest = candles[-1]
        closes = [candle.close for candle in candles]
        trend = ema(closes, self.config.trend_ema_period)[-1]
        current_atr = atr(candles, self.config.atr_period)[-1]
        current_relative_volume = relative_volume(
            candles,
            self.config.volume_period,
        )[-1]
        indicators: dict[str, Decimal | None] = {
            "trend_ema": trend,
            "atr": current_atr,
            "relative_volume": current_relative_volume,
            "range_high": None,
            "range_low": None,
        }
        if len(candles) <= self.config.range_period:
            return self._hold(
                latest,
                "Histórico insuficiente para a faixa de rompimento.",
                indicators,
            )

        previous_range = candles[-self.config.range_period - 1 : -1]
        range_high = max(candle.high for candle in previous_range)
        range_low = min(candle.low for candle in previous_range)
        indicators["range_high"] = range_high
        indicators["range_low"] = range_low
        if trend is None or current_atr is None or current_relative_volume is None:
            return self._hold(
                latest,
                "Histórico insuficiente para confirmar o rompimento.",
                indicators,
            )
        if current_relative_volume < self.config.minimum_relative_volume:
            return self._hold(
                latest,
                "Rompimento sem volume relativo suficiente.",
                indicators,
            )
        if not target_covers_costs(
            price=latest.close,
            current_atr=current_atr,
            take_atr_multiple=self.config.take_atr_multiple,
            projected_round_trip_cost_rate=(self.config.projected_round_trip_cost_rate),
            minimum_multiple=self.config.minimum_target_cost_multiple,
        ):
            return self._hold(
                latest,
                "Alvo do rompimento insuficiente para os custos projetados.",
                indicators,
            )

        action = SignalAction.HOLD
        if latest.close > range_high and latest.close > trend:
            action = SignalAction.BUY
        elif latest.close < range_low and latest.close < trend:
            action = SignalAction.SELL
        if action is SignalAction.HOLD:
            return self._hold(
                latest,
                "Nenhum rompimento confirmado pela tendência.",
                indicators,
            )
        return atr_entry_signal(
            latest,
            action=action,
            current_atr=current_atr,
            stop_atr_multiple=self.config.stop_atr_multiple,
            take_atr_multiple=self.config.take_atr_multiple,
            strategy=self.name,
            reason="Rompimento confirmado por tendência e volume relativo.",
            indicators=indicators,
        )

    def _hold(
        self,
        candle: Candle,
        reason: str,
        indicators: dict[str, Decimal | None],
    ) -> Signal:
        return hold_signal(
            candle,
            strategy=self.name,
            reason=reason,
            indicators=indicators,
        )
