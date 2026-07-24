"""Envio seguro de notificações por Discord Webhook."""

import httpx
from pydantic import SecretStr
from typing_extensions import Self

from trading_bot.domain import Trade
from trading_bot.notifications.discord_transport import DiscordWebhookTransport
from trading_bot.notifications.formatter import DiscordTradeFormatter
from trading_bot.notifications.settings import DiscordSettings


class DiscordWebhookNotifier:
    """Notifica trades encerrados sem expor a URL secreta em erros."""

    name = "discord"

    def __init__(
        self,
        webhook_url: SecretStr,
        *,
        formatter: DiscordTradeFormatter | None = None,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._formatter = formatter or DiscordTradeFormatter()
        self._transport = DiscordWebhookTransport(
            webhook_url,
            client=client,
            timeout=timeout,
        )

    @classmethod
    def from_settings(
        cls,
        settings: DiscordSettings,
        *,
        formatter: DiscordTradeFormatter | None = None,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> Self:
        """Cria o canal a partir de configurações já validadas."""

        return cls(
            settings.discord_webhook_url,
            formatter=formatter,
            client=client,
            timeout=timeout,
        )

    def notify_trade(self, trade: Trade) -> None:
        """Envia um único trade encerrado ao Discord."""

        self._transport.post(self._formatter.format(trade))

    def close(self) -> None:
        """Fecha somente o cliente HTTP criado pelo próprio notificador."""

        self._transport.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
