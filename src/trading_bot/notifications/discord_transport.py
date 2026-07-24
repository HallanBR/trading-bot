"""Transporte HTTP compartilhado pelos webhooks do Discord."""

from collections.abc import Mapping

import httpx
from pydantic import SecretStr

from trading_bot.notifications.exceptions import (
    NotificationError,
    NotificationRateLimitError,
)


class DiscordWebhookTransport:
    """Envia payloads sem revelar o webhook em exceções ou logs."""

    def __init__(
        self,
        webhook_url: SecretStr,
        *,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._webhook_url = webhook_url
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def post(self, payload: Mapping[str, object]) -> None:
        """Envia um payload JSON e converte falhas em erros seguros."""

        try:
            response = self._client.post(
                self._webhook_url.get_secret_value(),
                json=dict(payload),
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
        """Fecha somente o cliente HTTP criado pelo transporte."""

        if self._owns_client:
            self._client.close()

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
