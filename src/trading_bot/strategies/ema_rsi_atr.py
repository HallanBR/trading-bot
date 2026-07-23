"""Estratégia inicial baseada em cruzamento de EMA, RSI e ATR."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from trading_bot.domain import Candle, Signal, SignalAction
from trading_bot.indicators import atr, ema, rsi


@dataclass(frozen=True, slots=True)
class EmaRsiAtrConfig:
    """Parâmetros explícitos e validáveis da estratégia inicial."""

    fast_ema_period: int = 9
    slow_ema_period: int = 21
    rsi_period: int = 14
    atr_period: int = 14
    buy_rsi_min: Decimal = Decimal(50)
    buy_rsi_max: Decimal = Decimal(70)
    sell_rsi_min: Decimal = Decimal(30)
    sell_rsi_max: Decimal = Decimal(50)
    stop_atr_multiple: Decimal = Decimal("1.5")
    take_atr_multiple: Decimal = Decimal(3)

    def __post_init__(self) -> None:
        periods = (
            self.fast_ema_period,
            self.slow_ema_period,
            self.rsi_period,
            self.atr_period,
        )
        if any(
            isinstance(period, bool) or not isinstance(period, int) or period <= 0
            for period in periods
        ):
            raise ValueError("Todos os períodos devem ser inteiros positivos.")
        if self.fast_ema_period >= self.slow_ema_period:
            raise ValueError("A EMA rápida deve ter período menor que a EMA lenta.")
        if not Decimal(0) <= self.buy_rsi_min < self.buy_rsi_max <= Decimal(100):
            raise ValueError("Faixa de RSI para compra inválida.")
        if not Decimal(0) <= self.sell_rsi_min < self.sell_rsi_max <= Decimal(100):
            raise ValueError("Faixa de RSI para venda inválida.")
        if self.stop_atr_multiple <= 0 or self.take_atr_multiple <= 0:
            raise ValueError("Multiplicadores de ATR devem ser positivos.")


class EmaRsiAtrStrategy:
    """Gera sinais no fechamento do candle mais recente."""

    name = "EMA_RSI_ATR"

    def __init__(self, config: EmaRsiAtrConfig | None = None) -> None:
        self.config = config or EmaRsiAtrConfig()

    def generate_signal(self, candles: Sequence[Candle]) -> Signal:
        if not candles:
            raise ValueError("Ao menos um candle é necessário.")
        self._validate_candle_series(candles)

        closes = [candle.close for candle in candles]
        fast_values = ema(closes, self.config.fast_ema_period)
        slow_values = ema(closes, self.config.slow_ema_period)
        rsi_values = rsi(closes, self.config.rsi_period)
        atr_values = atr(candles, self.config.atr_period)
        latest = candles[-1]

        indicators = {
            "ema_fast": fast_values[-1],
            "ema_slow": slow_values[-1],
            "rsi": rsi_values[-1],
            "atr": atr_values[-1],
        }
        if len(candles) < 2 or any(value is None for value in indicators.values()):
            return self._hold(latest, "Histórico insuficiente.", indicators)

        previous_fast = fast_values[-2]
        previous_slow = slow_values[-2]
        current_fast = fast_values[-1]
        current_slow = slow_values[-1]
        current_rsi = rsi_values[-1]
        current_atr = atr_values[-1]

        if previous_fast is None or previous_slow is None:
            return self._hold(
                latest, "Histórico insuficiente para cruzamento.", indicators
            )

        assert current_fast is not None
        assert current_slow is not None
        assert current_rsi is not None
        assert current_atr is not None

        crossed_up = previous_fast <= previous_slow and current_fast > current_slow
        crossed_down = previous_fast >= previous_slow and current_fast < current_slow

        if (
            crossed_up
            and self.config.buy_rsi_min <= current_rsi <= self.config.buy_rsi_max
        ):
            return self._entry(
                latest,
                SignalAction.BUY,
                current_atr,
                "EMA rápida cruzou acima da lenta com RSI no filtro de compra.",
                indicators,
            )
        if (
            crossed_down
            and self.config.sell_rsi_min <= current_rsi <= self.config.sell_rsi_max
        ):
            return self._entry(
                latest,
                SignalAction.SELL,
                current_atr,
                "EMA rápida cruzou abaixo da lenta com RSI no filtro de venda.",
                indicators,
            )
        return self._hold(latest, "Condições de entrada não confirmadas.", indicators)

    def _entry(
        self,
        candle: Candle,
        action: SignalAction,
        current_atr: Decimal,
        reason: str,
        indicators: dict[str, Decimal | None],
    ) -> Signal:
        stop_distance = current_atr * self.config.stop_atr_multiple
        take_distance = current_atr * self.config.take_atr_multiple
        if action is SignalAction.BUY:
            stop_loss = candle.close - stop_distance
            take_profit = candle.close + take_distance
        else:
            stop_loss = candle.close + stop_distance
            take_profit = candle.close - take_distance

        if stop_loss <= 0 or take_profit <= 0:
            return self._hold(
                candle,
                "ATR gerou níveis de preço inválidos.",
                indicators,
            )
        return Signal(
            symbol=candle.symbol,
            interval=candle.interval,
            action=action,
            generated_at=candle.close_time,
            price=candle.close,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=self.name,
            reason=reason,
            indicators=indicators,
        )

    def _hold(
        self,
        candle: Candle,
        reason: str,
        indicators: dict[str, Decimal | None],
    ) -> Signal:
        return Signal(
            symbol=candle.symbol,
            interval=candle.interval,
            action=SignalAction.HOLD,
            generated_at=candle.close_time,
            price=candle.close,
            strategy=self.name,
            reason=reason,
            indicators=indicators,
        )

    @staticmethod
    def _validate_candle_series(candles: Sequence[Candle]) -> None:
        first = candles[0]
        previous_time = first.open_time
        for candle in candles:
            if candle.symbol != first.symbol or candle.interval != first.interval:
                raise ValueError("Todos os candles devem pertencer à mesma série.")
        for candle in candles[1:]:
            if candle.open_time <= previous_time:
                raise ValueError("Candles devem estar em ordem cronológica.")
            previous_time = candle.open_time
