"""Testes da distribuição resiliente do monitoramento."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from trading_bot.monitoring import (
    MonitoringEvent,
    MonitoringEventType,
    MonitoringService,
)
from trading_bot.notifications import NotificationError


@dataclass
class FakeMonitoringNotifier:
    name: str
    should_fail: bool = False
    calls: int = 0

    def notify_events(self, events: Sequence[MonitoringEvent]) -> None:
        assert events
        self.calls += 1
        if self.should_fail:
            raise NotificationError("Falha segura.")


def test_monitoring_attempts_terminal_when_discord_fails() -> None:
    discord = FakeMonitoringNotifier("discord_monitoring", should_fail=True)
    terminal = FakeMonitoringNotifier("terminal")
    service = MonitoringService([discord, terminal])
    event = MonitoringEvent(
        event_type=MonitoringEventType.WAITING_SIGNAL,
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSDT",
        interval="1m",
        message="Aguardando sinal.",
    )

    results = service.publish([event])

    assert discord.calls == 1
    assert terminal.calls == 1
    assert results[0].success is False
    assert results[1].success is True
