"""Cliente para dados públicos do mercado Spot da Binance."""

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from typing_extensions import Self

from trading_bot.domain import Candle
from trading_bot.market_data.exceptions import BinanceAPIError, BinanceResponseError

BINANCE_MARKET_DATA_URL = "https://data-api.binance.vision"
KLINES_PATH = "/api/v3/klines"

SUPPORTED_INTERVALS = frozenset(
    {
        "1s",
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "6h",
        "8h",
        "12h",
        "1d",
        "3d",
        "1w",
        "1M",
    }
)


class BinanceMarketDataProvider:
    """Consulta candles públicos sem usar chave ou permitir envio de ordens."""

    def __init__(
        self,
        *,
        base_url: str = BINANCE_MARKET_DATA_URL,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"User-Agent": "HallanBR-trading-bot/0.1"},
        )

    def get_candles(
        self,
        symbol: str,
        interval: str,
        *,
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[Candle]:
        """Retorna candles em ordem cronológica usando ``GET /api/v3/klines``."""

        normalized_symbol = self._validate_symbol(symbol)
        self._validate_request(interval, limit, start_time, end_time)

        params: dict[str, str | int] = {
            "symbol": normalized_symbol,
            "interval": interval,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = self._to_milliseconds(start_time)
        if end_time is not None:
            params["endTime"] = self._to_milliseconds(end_time)

        try:
            response = self._client.get(KLINES_PATH, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BinanceAPIError(self._error_message(exc.response)) from exc
        except httpx.HTTPError as exc:
            raise BinanceAPIError(f"Falha ao acessar a Binance: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BinanceResponseError("A Binance retornou JSON inválido.") from exc

        if not isinstance(payload, list):
            raise BinanceResponseError(
                "A Binance retornou candles em formato inválido."
            )

        return [
            self._parse_candle(normalized_symbol, interval, item) for item in payload
        ]

    def close(self) -> None:
        """Fecha somente o cliente HTTP criado pelo próprio provedor."""

        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _validate_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized or not normalized.isalnum():
            raise ValueError("O símbolo deve conter apenas letras e números.")
        return normalized

    @staticmethod
    def _validate_request(
        interval: str,
        limit: int,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> None:
        if interval not in SUPPORTED_INTERVALS:
            allowed = ", ".join(sorted(SUPPORTED_INTERVALS))
            raise ValueError(f"Intervalo inválido. Valores aceitos: {allowed}.")
        if not 1 <= limit <= 1000:
            raise ValueError("O limite deve estar entre 1 e 1000.")
        if start_time and end_time and start_time >= end_time:
            raise ValueError("start_time deve ser anterior a end_time.")

    @staticmethod
    def _to_milliseconds(value: datetime) -> int:
        if value.tzinfo is None:
            raise ValueError("Datas devem incluir fuso horário.")
        return int(value.timestamp() * 1000)

    @staticmethod
    def _parse_candle(symbol: str, interval: str, item: Any) -> Candle:
        if (
            not isinstance(item, Sequence)
            or isinstance(item, (str, bytes))
            or len(item) < 7
        ):
            raise BinanceResponseError("Um candle retornado está incompleto.")

        try:
            return Candle(
                symbol=symbol,
                interval=interval,
                open_time=datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc),
                close_time=datetime.fromtimestamp(item[6] / 1000, tz=timezone.utc),
                open=Decimal(str(item[1])),
                high=Decimal(str(item[2])),
                low=Decimal(str(item[3])),
                close=Decimal(str(item[4])),
                volume=Decimal(str(item[5])),
            )
        except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
            raise BinanceResponseError("Um candle contém valores inválidos.") from exc

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict) and "msg" in payload:
            return f"Binance respondeu {response.status_code}: {payload['msg']}"
        return f"Binance respondeu com HTTP {response.status_code}."
