"""Canal Discord exclusivo para a atividade operacional."""

from collections.abc import Sequence

import httpx
from pydantic import SecretStr

from trading_bot.monitoring.events import MonitoringEvent
from trading_bot.monitoring.formatter import MonitoringFormatter
from trading_bot.notifications.discord_transport import DiscordWebhookTransport


class DiscordMonitoringNotifier:
    """Envia lotes de atividade para um webhook diferente dos resultados."""

    name = "discord_monitoring"

    def __init__(
        self,
        webhook_url: SecretStr,
        *,
        formatter: MonitoringFormatter | None = None,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._formatter = formatter or MonitoringFormatter()
        self._transport = DiscordWebhookTransport(
            webhook_url,
            client=client,
            timeout=timeout,
        )

    def notify_events(self, events: Sequence[MonitoringEvent]) -> None:
        """Publica um lote em uma única requisição ao Discord."""

        if events:
            self._transport.post(self._formatter.discord_payload(events))

    def close(self) -> None:
        """Libera o cliente HTTP interno."""

        self._transport.close()
