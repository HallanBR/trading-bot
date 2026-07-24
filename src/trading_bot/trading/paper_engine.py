"""Orquestração incremental de candles, estratégia e notificações."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from trading_bot.domain import Candle, Trade
from trading_bot.execution import PaperExecutor
from trading_bot.notifications import NotificationResult, NotificationService
from trading_bot.strategies import Strategy


@dataclass(frozen=True, slots=True)
class PaperTradingUpdate:
    """Resultado observável de uma atualização do mercado."""

    primed_candles: int = 0
    processed_candles: int = 0
    closed_trades: tuple[Trade, ...] = ()
    notifications: tuple[NotificationResult, ...] = ()


class PaperTradingEngine:
    """Processa somente candles novos e nunca opera o histórico de aquecimento."""

    def __init__(
        self,
        strategy: Strategy,
        executor: PaperExecutor,
        *,
        notifications: NotificationService | None = None,
        max_history: int = 1_000,
    ) -> None:
        if max_history <= 1:
            raise ValueError("max_history deve ser maior que um.")
        self.strategy = strategy
        self.executor = executor
        self.notifications = notifications
        self.max_history = max_history
        self._history: list[Candle] = []
        self._last_processed_open_time: datetime | None = None
        self._initialized = False

    def process_candles(self, candles: Sequence[Candle]) -> PaperTradingUpdate:
        """Aquece na primeira chamada e processa apenas candles novos depois."""

        self._validate_series(candles)
        if not candles:
            return PaperTradingUpdate()
        if not self._initialized:
            self._prime(candles)
            return PaperTradingUpdate(primed_candles=len(self._history))

        new_candles = [
            candle
            for candle in candles
            if self._last_processed_open_time is None
            or candle.open_time > self._last_processed_open_time
        ]
        closed_trades: list[Trade] = []
        notification_results: list[NotificationResult] = []

        for candle in new_candles:
            self._append_history(candle)
            trades = self.executor.process_candle(candle)
            closed_trades.extend(trades)
            if self.notifications is not None:
                for trade in trades:
                    notification_results.extend(self.notifications.notify_trade(trade))

            if (
                not self.executor.has_open_position
                and not self.executor.has_pending_signal
            ):
                signal = self.strategy.generate_signal(self._history)
                self.executor.queue_signal(signal)
            self._last_processed_open_time = candle.open_time

        return PaperTradingUpdate(
            processed_candles=len(new_candles),
            closed_trades=tuple(closed_trades),
            notifications=tuple(notification_results),
        )

    def _prime(self, candles: Sequence[Candle]) -> None:
        self._history = list(candles[-self.max_history :])
        self._last_processed_open_time = self._history[-1].open_time
        self._initialized = True

    def _append_history(self, candle: Candle) -> None:
        if self._history:
            reference = self._history[0]
            if (
                candle.symbol != reference.symbol
                or candle.interval != reference.interval
            ):
                raise ValueError("O candle novo não pertence à série inicial.")
        self._history.append(candle)
        if len(self._history) > self.max_history:
            del self._history[: len(self._history) - self.max_history]

    @staticmethod
    def _validate_series(candles: Sequence[Candle]) -> None:
        if not candles:
            return
        first = candles[0]
        previous_time = first.open_time
        for candle in candles:
            if candle.symbol != first.symbol or candle.interval != first.interval:
                raise ValueError("Todos os candles devem pertencer à mesma série.")
        for candle in candles[1:]:
            if candle.open_time <= previous_time:
                raise ValueError("Candles devem estar em ordem cronológica.")
            previous_time = candle.open_time
