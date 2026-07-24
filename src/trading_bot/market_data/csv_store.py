"""Armazenamento portátil de candles históricos em CSV."""

import csv
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from trading_bot.domain import Candle

CSV_FIELDS = (
    "symbol",
    "interval",
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


class CandleCsvStore:
    """Lê e grava candles sem converter valores financeiros para ``float``."""

    def write(self, path: str | Path, candles: Sequence[Candle]) -> Path:
        """Substitui o destino de forma atômica após validar toda a série."""

        destination = Path(path)
        self._validate_series(candles)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")

        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for candle in candles:
                writer.writerow(
                    {
                        "symbol": candle.symbol,
                        "interval": candle.interval,
                        "open_time": candle.open_time.isoformat(),
                        "close_time": candle.close_time.isoformat(),
                        "open": str(candle.open),
                        "high": str(candle.high),
                        "low": str(candle.low),
                        "close": str(candle.close),
                        "volume": str(candle.volume),
                    }
                )
        temporary.replace(destination)
        return destination

    def read(self, path: str | Path) -> list[Candle]:
        """Reconstrói e valida uma série previamente gravada."""

        source = Path(path)
        candles: list[Candle] = []
        with source.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != list(CSV_FIELDS):
                raise ValueError("O CSV não possui o cabeçalho esperado.")
            for line_number, row in enumerate(reader, start=2):
                try:
                    candles.append(
                        Candle(
                            symbol=self._required(row, "symbol"),
                            interval=self._required(row, "interval"),
                            open_time=self._datetime(row, "open_time"),
                            close_time=self._datetime(row, "close_time"),
                            open=self._decimal(row, "open"),
                            high=self._decimal(row, "high"),
                            low=self._decimal(row, "low"),
                            close=self._decimal(row, "close"),
                            volume=self._decimal(row, "volume"),
                        )
                    )
                except (InvalidOperation, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Candle inválido na linha {line_number}: {exc}"
                    ) from exc
        self._validate_series(candles)
        return candles

    @staticmethod
    def _required(row: dict[str, str | None], name: str) -> str:
        value = row.get(name)
        if value is None or not value.strip():
            raise ValueError(f"{name} é obrigatório.")
        return value.strip()

    @classmethod
    def _datetime(cls, row: dict[str, str | None], name: str) -> datetime:
        parsed = datetime.fromisoformat(cls._required(row, name))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"{name} deve incluir fuso horário.")
        return parsed

    @classmethod
    def _decimal(cls, row: dict[str, str | None], name: str) -> Decimal:
        value = Decimal(cls._required(row, name))
        if not value.is_finite():
            raise ValueError(f"{name} deve ser finito.")
        return value

    @staticmethod
    def _validate_series(candles: Sequence[Candle]) -> None:
        if not candles:
            return
        first = candles[0]
        previous_open_time: datetime | None = None
        for candle in candles:
            if candle.symbol != first.symbol or candle.interval != first.interval:
                raise ValueError("Todos os candles devem pertencer à mesma série.")
            if candle.close_time <= candle.open_time:
                raise ValueError("O fechamento deve ocorrer após a abertura.")
            if candle.low > min(candle.open, candle.close, candle.high):
                raise ValueError("Preço mínimo inconsistente.")
            if candle.high < max(candle.open, candle.close, candle.low):
                raise ValueError("Preço máximo inconsistente.")
            if min(candle.open, candle.high, candle.low, candle.close) <= 0:
                raise ValueError("Preços devem ser positivos.")
            if candle.volume < 0:
                raise ValueError("Volume não pode ser negativo.")
            if (
                previous_open_time is not None
                and candle.open_time <= previous_open_time
            ):
                raise ValueError("Candles devem estar em ordem e sem duplicatas.")
            previous_open_time = candle.open_time
