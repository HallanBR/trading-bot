"""Envio seguro de notificações por Discord Webhook."""

import httpx
from pydantic import SecretStr
from typing_extensions import Self

from trading_bot.domain import Trade
from trading_bot.notifications.exceptions import (
    NotificationError,
    NotificationRateLimitError,
)
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
        self._webhook_url = webhook_url
        self._formatter = formatter or DiscordTradeFormatter()
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

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

        try:
            response = self._client.post(
                self._webhook_url.get_secret_value(),
                json=self._formatter.format(trade),
            )
        except httpx.HTTPError as exc:
            raise NotificationError(
                "Falha de rede ao enviar a notificação ao Discord."
            ) from exc

        if response.status_code == 429:
            raise NotificationRateLimitError(self._retry_after(response))
        if not 200 <= response.status_code < 300:
            raise NotificationError(
                f"O Discord recusou a notificação com HTTP {response.status_code}."
            )

    def close(self) -> None:
        """Fecha somente o cliente HTTP criado pelo próprio notificador."""

        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        header = response.headers.get("Retry-After")
        if header is not None:
            try:
                return float(header)
            except ValueError:
                return None
        try:
            payload = response.json()
        except ValueError:
            return None
        value = payload.get("retry_after") if isinstance(payload, dict) else None
        return float(value) if isinstance(value, (int, float)) else None
