"""Testes da apresentação dos eventos operacionais."""

from datetime import datetime, timezone

from trading_bot.monitoring import (
    ConsoleMonitoringNotifier,
    MonitoringEvent,
    MonitoringEventType,
    MonitoringFormatter,
)


def event(index: int = 0) -> MonitoringEvent:
    return MonitoringEvent(
        event_type=MonitoringEventType.CANDLE_PROCESSED,
        occurred_at=datetime(2026, 1, 1, 20, index, tzinfo=timezone.utc),
        symbol="BTCUSDT",
        interval="1m",
        message="Candle processado.",
    )


def test_formatter_produces_expected_activity_line() -> None:
    formatter = MonitoringFormatter(display_timezone=timezone.utc)

    assert formatter.line(event()) == "20:00 | BTCUSDT 1m | Candle processado."


def test_console_writes_every_event() -> None:
    lines: list[str] = []
    console = ConsoleMonitoringNotifier(
        formatter=MonitoringFormatter(display_timezone=timezone.utc),
        writer=lines.append,
    )

    console.notify_events([event(0), event(1)])

    assert lines == [
        "20:00 | BTCUSDT 1m | Candle processado.",
        "20:01 | BTCUSDT 1m | Candle processado.",
    ]


def test_discord_payload_summarizes_oversized_batch() -> None:
    formatter = MonitoringFormatter(display_timezone=timezone.utc)
    events = [
        MonitoringEvent(
            event_type=MonitoringEventType.WAITING_SIGNAL,
            occurred_at=datetime(2026, 1, 1, 20, index % 60, tzinfo=timezone.utc),
            symbol="BTCUSDT",
            interval="1m",
            message=f"Aguardando sinal com contexto {index:03d}.",
        )
        for index in range(100)
    ]

    payload = formatter.discord_payload(events)
    content = str(payload["content"])

    assert len(content) < 2_000
    assert "eventos anteriores resumidos" in content
    assert "contexto 099" in content
