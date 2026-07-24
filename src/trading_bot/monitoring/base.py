"""Contrato comum dos destinos de monitoramento."""

from collections.abc import Sequence
from typing import Protocol

from trading_bot.monitoring.events import MonitoringEvent


class MonitoringNotifier(Protocol):
    """Canal capaz de receber um lote de eventos operacionais."""

    @property
    def name(self) -> str:
        """Nome estável do canal."""

    def notify_events(self, events: Sequence[MonitoringEvent]) -> None:
        """Publica eventos ou levanta ``NotificationError``."""
