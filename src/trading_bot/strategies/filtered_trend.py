"""Versão filtrada da estratégia EMA + RSI + ATR."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from trading_bot.domain import Candle, Signal, SignalAction
from trading_bot.indicators import ema, relative_volume, rolling_vwap
from trading_bot.strategies._common import (
    hold_signal,
    target_covers_costs,
    validate_candle_series,
)
from trading_bot.strategies.ema_rsi_atr import EmaRsiAtrConfig, EmaRsiAtrStrategy


@dataclass(frozen=True, slots=True)
class FilteredTrendConfig:
    """Filtros conservadores aplicados somente após o sinal-base."""

    base: EmaRsiAtrConfig = field(default_factory=EmaRsiAtrConfig)
    trend_ema_period: int = 50
    trend_slope_lookback: int = 5
    vwap_period: int = 20
    volume_period: int = 20
    minimum_relative_volume: Decimal = Decimal("1.10")
    minimum_atr_percent: Decimal = Decimal("0.03")
    maximum_atr_percent: Decimal = Decimal("0.80")
    projected_round_trip_cost_rate: Decimal = Decimal("0.003")
    minimum_target_cost_multiple: Decimal = Decimal("1.25")

    def __post_init__(self) -> None:
        periods = (
            self.trend_ema_period,
            self.trend_slope_lookback,
            self.vwap_period,
            self.volume_period,
        )
        if any(
            isinstance(period, bool) or not isinstance(period, int) or period <= 0
            for period in periods
        ):
            raise ValueError("Períodos dos filtros devem ser inteiros positivos.")
        if self.minimum_relative_volume <= 0:
            raise ValueError("minimum_relative_volume deve ser positivo.")
        if not (Decimal(0) <= self.minimum_atr_percent < self.maximum_atr_percent):
            raise ValueError("Faixa percentual de ATR inválida.")
        if not Decimal(0) <= self.projected_round_trip_cost_rate < Decimal(1):
            raise ValueError("Custo projetado deve estar entre zero e um.")
        if self.minimum_target_cost_multiple <= 0:
            raise ValueError("Múltiplo mínimo de custos deve ser positivo.")


class FilteredTrendStrategy:
    """Exige tendência, VWAP, volume, volatilidade e cobertura de custos."""

    name = "EMA_RSI_ATR_FILTERED"

    def __init__(self, config: FilteredTrendConfig | None = None) -> None:
        self.config = config or FilteredTrendConfig()
        self._base = EmaRsiAtrStrategy(self.config.base)

    def generate_signal(self, candles: Sequence[Candle]) -> Signal:
        validate_candle_series(candles)
        base_signal = self._base.generate_signal(candles)
        latest = candles[-1]
        indicators = dict(base_signal.indicators)

        if base_signal.action is SignalAction.HOLD:
            return hold_signal(
                latest,
                strategy=self.name,
                reason=base_signal.reason,
                indicators=indicators,
            )

        closes = [candle.close for candle in candles]
        trend_values = ema(closes, self.config.trend_ema_period)
        vwap_values = rolling_vwap(candles, self.config.vwap_period)
        volume_values = relative_volume(candles, self.config.volume_period)
        slope_index = len(candles) - 1 - self.config.trend_slope_lookback
        trend = trend_values[-1]
        earlier_trend = None if slope_index < 0 else trend_values[slope_index]
        current_vwap = vwap_values[-1]
        current_relative_volume = volume_values[-1]
        current_atr = indicators.get("atr")
        indicators.update(
            {
                "trend_ema": trend,
                "trend_ema_previous": earlier_trend,
                "vwap": current_vwap,
                "relative_volume": current_relative_volume,
            }
        )
        context_values = (
            trend,
            earlier_trend,
            current_vwap,
            current_relative_volume,
            current_atr,
        )
        if any(value is None for value in context_values):
            return self._blocked(
                latest,
                "Histórico insuficiente para os filtros de mercado.",
                indicators,
            )

        assert trend is not None
        assert earlier_trend is not None
        assert current_vwap is not None
        assert current_relative_volume is not None
        assert current_atr is not None
        atr_percent = (current_atr / latest.close) * Decimal(100)
        indicators["atr_percent"] = atr_percent

        if current_relative_volume < self.config.minimum_relative_volume:
            return self._blocked(
                latest,
                "Volume relativo abaixo do mínimo.",
                indicators,
            )
        if not (
            self.config.minimum_atr_percent
            <= atr_percent
            <= self.config.maximum_atr_percent
        ):
            return self._blocked(
                latest,
                "Volatilidade fora da faixa operacional.",
                indicators,
            )
        if not target_covers_costs(
            price=latest.close,
            current_atr=current_atr,
            take_atr_multiple=self.config.base.take_atr_multiple,
            projected_round_trip_cost_rate=(self.config.projected_round_trip_cost_rate),
            minimum_multiple=self.config.minimum_target_cost_multiple,
        ):
            return self._blocked(
                latest,
                "Alvo estimado insuficiente para cobrir custos com margem.",
                indicators,
            )

        if base_signal.action is SignalAction.BUY:
            aligned = (
                latest.close > trend > earlier_trend and latest.close > current_vwap
            )
        else:
            aligned = (
                latest.close < trend < earlier_trend and latest.close < current_vwap
            )
        if not aligned:
            return self._blocked(
                latest,
                "Tendência e VWAP não confirmaram o sinal.",
                indicators,
            )

        return Signal(
            symbol=base_signal.symbol,
            interval=base_signal.interval,
            action=base_signal.action,
            generated_at=base_signal.generated_at,
            price=base_signal.price,
            stop_loss=base_signal.stop_loss,
            take_profit=base_signal.take_profit,
            strategy=self.name,
            reason=f"{base_signal.reason} Filtros de mercado confirmados.",
            indicators=indicators,
        )

    def _blocked(
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
