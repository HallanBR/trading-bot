"""Contrato comum dos canais de notificação."""

from typing import Protocol

from trading_bot.domain import Trade


class TradeNotifier(Protocol):
    """Canal que recebe somente operações já encerradas."""

    @property
    def name(self) -> str:
        """Nome estável do canal."""

    def notify_trade(self, trade: Trade) -> None:
        """Envia a notificação ou levanta ``NotificationError``."""
