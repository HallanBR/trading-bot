"""Contratos do conjunto de dados usado pelo aprendizado futuro."""

from typing import Protocol

from trading_bot.domain import Trade


class LosingTradeStore(Protocol):
    """Destino capaz de registrar somente operações perdedoras."""

    def save_loss(self, trade: Trade) -> bool:
        """Salva uma perda nova e retorna se um registro foi criado."""
