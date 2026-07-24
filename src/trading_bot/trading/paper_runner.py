"""Polling de candles públicos para o ciclo de paper trading."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import Event
from typing import Protocol

from trading_bot.domain import Candle
from trading_bot.monitoring import MonitoringService
from trading_bot.trading.paper_engine import PaperTradingEngine, PaperTradingUpdate


class CandleProvider(Protocol):
    """Fonte pública compatível com o runner."""

    def get_candles(
        self,
        symbol: str,
        interval: str,
        *,
        limit: int = 500,
    ) -> list[Candle]:
        """Retorna candles em ordem cronológica."""


@dataclass(frozen=True, slots=True)
class PaperTradingConfig:
    """Parâmetros de polling que não concedem acesso a ordens reais."""

    symbol: str = "BTCUSDT"
    interval: str = "5m"
    lookback: int = 300
    poll_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.symbol or not self.symbol.isalnum():
            raise ValueError("symbol deve conter apenas letras e números.")
        if not self.interval:
            raise ValueError("interval é obrigatório.")
        if not 2 <= self.lookback <= 1_000:
            raise ValueError("lookback deve estar entre 2 e 1000.")
        if self.poll_seconds <= 0:
            raise ValueError("poll_seconds deve ser positivo.")


class PaperTradingRunner:
    """Consulta candles e entrega apenas os já encerrados ao motor paper."""

    def __init__(
        self,
        provider: CandleProvider,
        engine: PaperTradingEngine,
        *,
        config: PaperTradingConfig | None = None,
        clock: Callable[[], datetime] | None = None,
        monitoring: MonitoringService | None = None,
        error_writer: Callable[[str], None] = print,
    ) -> None:
        self.provider = provider
        self.engine = engine
        self.config = config or PaperTradingConfig()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.monitoring = monitoring
        self.error_writer = error_writer

    def poll_once(self) -> PaperTradingUpdate:
        """Executa uma consulta e ignora o candle ainda em formação."""

        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("O relógio deve retornar data com fuso horário.")
        candles = self.provider.get_candles(
            self.config.symbol,
            self.config.interval,
            limit=self.config.lookback,
        )
        completed = [candle for candle in candles if candle.close_time <= now]
        update = self.engine.process_candles(completed)
        if self.monitoring is None:
            return update
        results = self.monitoring.publish(update.monitoring_events)
        return replace(update, monitoring_results=results)

    def run_forever(self, stop_event: Event) -> None:
        """Executa polling até ``stop_event`` ser acionado."""

        while not stop_event.is_set():
            update = self.poll_once()
            for result in update.monitoring_results:
                if not result.success:
                    self.error_writer(
                        f"Falha no canal {result.channel}: {result.error}"
                    )
            stop_event.wait(self.config.poll_seconds)
