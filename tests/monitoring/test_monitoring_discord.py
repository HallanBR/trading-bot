"""Testes do webhook exclusivo de monitoramento."""

import json
from datetime import datetime, timezone

import httpx
from pydantic import SecretStr

from trading_bot.monitoring import (
    DiscordMonitoringNotifier,
    MonitoringEvent,
    MonitoringEventType,
)

WEBHOOK = "https://discord.com/api/" + "webhooks/456/monitoring-secret"


def test_monitoring_posts_plain_activity_without_trade_embed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/webhooks/456/monitoring-secret"
        payload = json.loads(request.content)
        assert "Monitoramento do Trading Bot" in payload["content"]
        assert "Candle processado" in payload["content"]
        assert "embeds" not in payload
        return httpx.Response(204)

    notifier = DiscordMonitoringNotifier(
        SecretStr(WEBHOOK),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    notifier.notify_events(
        [
            MonitoringEvent(
                event_type=MonitoringEventType.CANDLE_PROCESSED,
                occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                symbol="BTCUSDT",
                interval="1m",
                message="Candle processado.",
            )
        ]
    )
