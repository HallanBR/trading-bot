"""Testes do cliente de Discord Webhook."""

import json

import httpx
import pytest
from pydantic import SecretStr

from trading_bot.domain import Trade
from trading_bot.notifications import (
    DiscordWebhookNotifier,
    NotificationError,
    NotificationRateLimitError,
)

WEBHOOK = "https://discord.com/api/" + "webhooks/123/secret-token"


def notifier(handler: httpx.MockTransport) -> DiscordWebhookNotifier:
    client = httpx.Client(transport=handler)
    return DiscordWebhookNotifier(SecretStr(WEBHOOK), client=client)


def test_notifier_posts_formatted_trade(winning_trade: Trade) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/webhooks/123/secret-token"
        payload = json.loads(request.content)
        assert payload["embeds"][0]["title"] == "🟢 Operação vitoriosa"
        return httpx.Response(204)

    notifier(httpx.MockTransport(handler)).notify_trade(winning_trade)


def test_notifier_hides_webhook_from_http_error(winning_trade: Trade) -> None:
    channel = notifier(
        httpx.MockTransport(lambda _: httpx.Response(500, text="failure"))
    )

    with pytest.raises(NotificationError) as error:
        channel.notify_trade(winning_trade)

    assert "secret-token" not in str(error.value)
    assert "HTTP 500" in str(error.value)


def test_notifier_hides_webhook_from_network_error(winning_trade: Trade) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("failed", request=request)

    channel = notifier(httpx.MockTransport(handler))

    with pytest.raises(NotificationError) as error:
        channel.notify_trade(winning_trade)

    assert "secret-token" not in str(error.value)


def test_notifier_exposes_safe_rate_limit_delay(winning_trade: Trade) -> None:
    channel = notifier(
        httpx.MockTransport(
            lambda _: httpx.Response(429, headers={"Retry-After": "2.5"})
        )
    )

    with pytest.raises(NotificationRateLimitError) as error:
        channel.notify_trade(winning_trade)

    assert error.value.retry_after == 2.5
    assert "2.5 segundos" in str(error.value)
