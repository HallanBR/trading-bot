"""Estratégia candidata de reversão à média para mercados laterais."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from trading_bot.domain import Candle, Signal, SignalAction
from trading_bot.indicators import atr, bollinger_bands, ema, rsi
from trading_bot.strategies._common import (
    atr_entry_signal,
    hold_signal,
    target_covers_costs,
    validate_candle_series,
)


@dataclass(frozen=True, slots=True)
class MeanReversionConfig:
    band_period: int = 20
    standard_deviations: Decimal = Decimal(2)
    rsi_period: int = 14
    atr_period: int = 14
    regime_ema_period: int = 50
    maximum_trend_gap_percent: Decimal = Decimal("0.35")
    buy_rsi_maximum: Decimal = Decimal(30)
    sell_rsi_minimum: Decimal = Decimal(70)
    stop_atr_multiple: Decimal = Decimal("1.5")
    take_atr_multiple: Decimal = Decimal("2.5")
    projected_round_trip_cost_rate: Decimal = Decimal("0.003")
    minimum_target_cost_multiple: Decimal = Decimal("1.25")

    def __post_init__(self) -> None:
        periods = (
            self.band_period,
            self.rsi_period,
            self.atr_period,
            self.regime_ema_period,
        )
        if any(
            isinstance(period, bool) or not isinstance(period, int) or period <= 0
            for period in periods
        ):
            raise ValueError("Períodos devem ser inteiros positivos.")
        if not Decimal(0) <= self.buy_rsi_maximum < self.sell_rsi_minimum <= 100:
            raise ValueError("Limites de RSI inválidos.")
        positive = (
            self.standard_deviations,
            self.maximum_trend_gap_percent,
            self.stop_atr_multiple,
            self.take_atr_multiple,
            self.minimum_target_cost_multiple,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("Limites da estratégia devem ser positivos.")
        if not Decimal(0) <= self.projected_round_trip_cost_rate < Decimal(1):
            raise ValueError("Custo projetado deve estar entre zero e um.")


class MeanReversionStrategy:
    """Busca retorno à média apenas quando o regime não está muito esticado."""

    name = "MEAN_REVERSION_BOLLINGER"

    def __init__(self, config: MeanReversionConfig | None = None) -> None:
        self.config = config or MeanReversionConfig()

    def generate_signal(self, candles: Sequence[Candle]) -> Signal:
        validate_candle_series(candles)
        latest = candles[-1]
        closes = [candle.close for candle in candles]
        middle_values, upper_values, lower_values = bollinger_bands(
            closes,
            self.config.band_period,
            self.config.standard_deviations,
        )
        current_rsi = rsi(closes, self.config.rsi_period)[-1]
        current_atr = atr(candles, self.config.atr_period)[-1]
        regime_ema = ema(closes, self.config.regime_ema_period)[-1]
        middle = middle_values[-1]
        upper = upper_values[-1]
        lower = lower_values[-1]
        indicators: dict[str, Decimal | None] = {
            "bollinger_middle": middle,
            "bollinger_upper": upper,
            "bollinger_lower": lower,
            "rsi": current_rsi,
            "atr": current_atr,
            "regime_ema": regime_ema,
            "trend_gap_percent": None,
        }
        context = (middle, upper, lower, current_rsi, current_atr, regime_ema)
        if any(value is None for value in context):
            return self._hold(
                latest,
                "Histórico insuficiente para reversão à média.",
                indicators,
            )

        assert middle is not None
        assert upper is not None
        assert lower is not None
        assert current_rsi is not None
        assert current_atr is not None
        assert regime_ema is not None
        trend_gap = (abs(latest.close - regime_ema) / latest.close) * Decimal(100)
        indicators["trend_gap_percent"] = trend_gap
        if trend_gap > self.config.maximum_trend_gap_percent:
            return self._hold(
                latest,
                "Regime direcional demais para reversão à média.",
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
                "Alvo de reversão insuficiente para os custos projetados.",
                indicators,
            )

        action = SignalAction.HOLD
        if latest.close < lower and current_rsi <= self.config.buy_rsi_maximum:
            action = SignalAction.BUY
        elif latest.close > upper and current_rsi >= self.config.sell_rsi_minimum:
            action = SignalAction.SELL
        if action is SignalAction.HOLD:
            return self._hold(
                latest,
                "Preço e RSI não confirmaram uma reversão.",
                indicators,
            )
        return atr_entry_signal(
            latest,
            action=action,
            current_atr=current_atr,
            stop_atr_multiple=self.config.stop_atr_multiple,
            take_atr_multiple=self.config.take_atr_multiple,
            strategy=self.name,
            reason="Extremo de Bollinger e RSI confirmado em regime lateral.",
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
