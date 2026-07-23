"""Contrato comum para estratégias de trading."""

from collections.abc import Sequence
from typing import Protocol

from trading_bot.domain import Candle, Signal


class Strategy(Protocol):
    """Estratégia que analisa candles sem executar ordens."""

    @property
    def name(self) -> str:
        """Nome estável usado em sinais, operações e relatórios."""

    def generate_signal(self, candles: Sequence[Candle]) -> Signal:
        """Gera uma decisão usando somente os candles recebidos."""
