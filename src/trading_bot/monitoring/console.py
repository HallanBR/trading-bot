"""Monitoramento local no terminal."""

from collections.abc import Callable, Sequence

from trading_bot.monitoring.events import MonitoringEvent
from trading_bot.monitoring.formatter import MonitoringFormatter


class ConsoleMonitoringNotifier:
    """Escreve cada atividade como uma linha curta no terminal."""

    name = "terminal"

    def __init__(
        self,
        *,
        formatter: MonitoringFormatter | None = None,
        writer: Callable[[str], None] = print,
    ) -> None:
        self._formatter = formatter or MonitoringFormatter()
        self._writer = writer

    def notify_events(self, events: Sequence[MonitoringEvent]) -> None:
        """Exibe todos os eventos sem agrupá-los ou descartá-los."""

        for event in events:
            self._writer(self._formatter.line(event))
