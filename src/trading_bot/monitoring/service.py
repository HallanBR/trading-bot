"""Distribuição resiliente dos eventos de monitoramento."""

from collections.abc import Sequence
from dataclasses import dataclass

from trading_bot.monitoring.base import MonitoringNotifier
from trading_bot.monitoring.events import MonitoringEvent
from trading_bot.notifications import NotificationError


@dataclass(frozen=True, slots=True)
class MonitoringResult:
    """Resultado seguro do envio para um destino de monitoramento."""

    channel: str
    success: bool
    error: str | None = None


class MonitoringService:
    """Tenta todos os destinos sem permitir que um deles interrompa o robô."""

    def __init__(self, notifiers: Sequence[MonitoringNotifier]) -> None:
        self._notifiers = tuple(notifiers)

    def publish(
        self,
        events: Sequence[MonitoringEvent],
    ) -> tuple[MonitoringResult, ...]:
        """Publica um lote e isola falhas de rede por canal."""

        if not events:
            return ()
        results: list[MonitoringResult] = []
        for notifier in self._notifiers:
            try:
                notifier.notify_events(events)
            except NotificationError as exc:
                results.append(
                    MonitoringResult(
                        channel=notifier.name,
                        success=False,
                        error=str(exc),
                    )
                )
            else:
                results.append(
                    MonitoringResult(
                        channel=notifier.name,
                        success=True,
                    )
                )
        return tuple(results)
