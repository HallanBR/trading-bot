"""Testes do polling de candles públicos."""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trading_bot.domain import Candle
from trading_bot.monitoring import (
    MonitoringEvent,
    MonitoringEventType,
    MonitoringService,
)
from trading_bot.trading import (
    PaperTradingConfig,
    PaperTradingRunner,
    PaperTradingUpdate,
)


class RecordingProvider:
    def __init__(self, candles: list[Candle]) -> None:
        self.candles = candles
        self.request: tuple[str, str, int] | None = None

    def get_candles(
        self,
        symbol: str,
        interval: str,
        *,
        limit: int = 500,
    ) -> list[Candle]:
        self.request = (symbol, interval, limit)
        return self.candles


class RecordingEngine:
    def __init__(self) -> None:
        self.received: list[Candle] = []

    def process_candles(self, candles: list[Candle]) -> PaperTradingUpdate:
        self.received = list(candles)
        events = (
            ()
            if not candles
            else (
                MonitoringEvent(
                    event_type=MonitoringEventType.CANDLE_PROCESSED,
                    occurred_at=candles[-1].close_time,
                    symbol=candles[-1].symbol,
                    interval=candles[-1].interval,
                    message="Candle processado.",
                ),
            )
        )
        return PaperTradingUpdate(
            primed_candles=len(candles),
            monitoring_events=events,
        )


class RecordingMonitoringNotifier:
    name = "recording"

    def __init__(self) -> None:
        self.events: list[MonitoringEvent] = []

    def notify_events(self, events: Sequence[MonitoringEvent]) -> None:
        self.events.extend(events)


def candle(index: int) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index)
    return Candle(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=open_time + timedelta(seconds=59),
        open=Decimal(10),
        high=Decimal(11),
        low=Decimal(9),
        close=Decimal(10),
        volume=Decimal(1),
    )


def test_poll_once_excludes_candle_still_in_formation() -> None:
    candles = [candle(0), candle(1)]
    provider = RecordingProvider(candles)
    engine = RecordingEngine()
    now = candles[0].close_time
    runner = PaperTradingRunner(
        provider,
        engine,  # type: ignore[arg-type]
        config=PaperTradingConfig(
            symbol="BTCUSDT",
            interval="1m",
            lookback=50,
            poll_seconds=1,
        ),
        clock=lambda: now,
    )

    update = runner.poll_once()

    assert provider.request == ("BTCUSDT", "1m", 50)
    assert engine.received == [candles[0]]
    assert update.primed_candles == 1


def test_poll_once_publishes_monitoring_events() -> None:
    candles = [candle(0)]
    provider = RecordingProvider(candles)
    engine = RecordingEngine()
    notifier = RecordingMonitoringNotifier()
    runner = PaperTradingRunner(
        provider,
        engine,  # type: ignore[arg-type]
        config=PaperTradingConfig(
            symbol="BTCUSDT",
            interval="1m",
            lookback=50,
            poll_seconds=1,
        ),
        clock=lambda: candles[0].close_time,
        monitoring=MonitoringService([notifier]),
    )

    update = runner.poll_once()

    assert len(notifier.events) == 1
    assert notifier.events[0].event_type is MonitoringEventType.CANDLE_PROCESSED
    assert update.monitoring_results[0].success is True
