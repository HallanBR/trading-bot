"""Estratégia segura usada quando nenhum candidato é elegível."""

from collections.abc import Sequence

from trading_bot.domain import Candle, Signal, SignalAction


class NoTradeStrategy:
    """Explicita que preservar o capital também é uma decisão do otimizador."""

    name = "NO_ELIGIBLE_CANDIDATE"

    def generate_signal(self, candles: Sequence[Candle]) -> Signal:
        if not candles:
            raise ValueError("Ao menos um candle é necessário.")
        latest = candles[-1]
        return Signal(
            symbol=latest.symbol,
            interval=latest.interval,
            action=SignalAction.HOLD,
            generated_at=latest.close_time,
            price=latest.close,
            strategy=self.name,
            reason="Nenhum candidato cumpriu os critérios no treino.",
        )
