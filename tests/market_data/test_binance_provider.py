"""Testes do provedor público de candles da Binance."""

from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from trading_bot.market_data.binance_provider import BinanceMarketDataProvider
from trading_bot.market_data.exceptions import BinanceAPIError, BinanceResponseError


def make_provider(handler: httpx.MockTransport) -> BinanceMarketDataProvider:
    client = httpx.Client(
        transport=handler,
        base_url="https://data-api.binance.vision",
    )
    return BinanceMarketDataProvider(client=client)


def test_get_candles_maps_binance_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/klines"
        assert request.url.params["symbol"] == "BTCUSDT"
        assert request.url.params["interval"] == "5m"
        assert request.url.params["limit"] == "1"
        return httpx.Response(
            200,
            json=[
                [
                    1_720_000_000_000,
                    "64000.10",
                    "64200.00",
                    "63950.50",
                    "64150.25",
                    "12.345",
                    1_720_000_299_999,
                    "0",
                    1,
                    "0",
                    "0",
                    "0",
                ]
            ],
        )

    provider = make_provider(httpx.MockTransport(handler))
    candles = provider.get_candles("btcusdt", "5m", limit=1)

    assert len(candles) == 1
    candle = candles[0]
    assert candle.symbol == "BTCUSDT"
    assert candle.open == Decimal("64000.10")
    assert candle.close == Decimal("64150.25")
    assert candle.open_time.tzinfo is timezone.utc


def test_get_candles_sends_time_range_in_milliseconds() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["startTime"] == str(int(start.timestamp() * 1000))
        assert request.url.params["endTime"] == str(int(end.timestamp() * 1000))
        return httpx.Response(200, json=[])

    provider = make_provider(httpx.MockTransport(handler))

    assert provider.get_candles("ETHUSDT", "1h", start_time=start, end_time=end) == []


@pytest.mark.parametrize(
    ("symbol", "interval", "limit"),
    [
        ("", "5m", 100),
        ("BTC/USDT", "5m", 100),
        ("BTCUSDT", "7m", 100),
        ("BTCUSDT", "5m", 0),
        ("BTCUSDT", "5m", 1001),
    ],
)
def test_get_candles_rejects_invalid_parameters(
    symbol: str, interval: str, limit: int
) -> None:
    provider = make_provider(
        httpx.MockTransport(lambda _: httpx.Response(200, json=[]))
    )

    with pytest.raises(ValueError):
        provider.get_candles(symbol, interval, limit=limit)


def test_get_candles_exposes_binance_error_message() -> None:
    provider = make_provider(
        httpx.MockTransport(
            lambda _: httpx.Response(
                400, json={"code": -1121, "msg": "Invalid symbol."}
            )
        )
    )

    with pytest.raises(BinanceAPIError, match="Invalid symbol"):
        provider.get_candles("UNKNOWNUSDT", "5m")


def test_get_candles_rejects_malformed_payload() -> None:
    provider = make_provider(
        httpx.MockTransport(lambda _: httpx.Response(200, json={"unexpected": True}))
    )

    with pytest.raises(BinanceResponseError):
        provider.get_candles("BTCUSDT", "5m")


def test_get_historical_candles_paginates_without_duplicates() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc)
    minute_ms = 60_000
    first_ms = int(start.timestamp() * 1000)
    calls: list[int] = []

    def payload(index: int) -> list[object]:
        open_ms = first_ms + (index * minute_ms)
        return [
            open_ms,
            "100",
            "101",
            "99",
            "100",
            "10",
            open_ms + minute_ms - 1,
        ]

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(int(request.url.params["startTime"]))
        page = [payload(0), payload(1)] if len(calls) == 1 else [payload(2)]
        return httpx.Response(200, json=page)

    provider = make_provider(httpx.MockTransport(handler))

    candles = provider.get_historical_candles(
        "BTCUSDT",
        "1m",
        start_time=start,
        end_time=end,
        page_limit=2,
    )

    assert len(candles) == 3
    assert len({candle.open_time for candle in candles}) == 3
    assert calls[1] == first_ms + minute_ms + 1


def test_get_historical_candles_respects_maximum() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)

    def handler(request: httpx.Request) -> httpx.Response:
        open_ms = int(request.url.params["startTime"])
        limit = int(request.url.params["limit"])
        return httpx.Response(
            200,
            json=[
                [
                    open_ms + (index * 60_000),
                    "100",
                    "101",
                    "99",
                    "100",
                    "10",
                    open_ms + ((index + 1) * 60_000) - 1,
                ]
                for index in range(limit)
            ],
        )

    provider = make_provider(httpx.MockTransport(handler))

    candles = provider.get_historical_candles(
        "BTCUSDT",
        "1m",
        start_time=start,
        end_time=end,
        page_limit=2,
        max_candles=3,
    )

    assert len(candles) == 3
