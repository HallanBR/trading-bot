"""Orquestração incremental de candles, estratégia e notificações."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from trading_bot.domain import Candle, PositionSide, SignalAction, Trade
from trading_bot.execution import PaperExecutor
from trading_bot.learning import LosingTradeStore
from trading_bot.monitoring import (
    MonitoringEvent,
    MonitoringEventType,
    MonitoringResult,
)
from trading_bot.notifications import NotificationResult, NotificationService
from trading_bot.strategies import Strategy
from trading_bot.trading.paper_state import (
    PaperCheckpointStore,
    PaperTradingState,
)


@dataclass(frozen=True, slots=True)
class PaperTradingUpdate:
    """Resultado observável de uma atualização do mercado."""

    primed_candles: int = 0
    processed_candles: int = 0
    closed_trades: tuple[Trade, ...] = ()
    recorded_trades: int = 0
    recorded_losses: int = 0
    notifications: tuple[NotificationResult, ...] = ()
    monitoring_events: tuple[MonitoringEvent, ...] = ()
    monitoring_results: tuple[MonitoringResult, ...] = ()


class PaperTradingEngine:
    """Processa somente candles novos e nunca opera o histórico de aquecimento."""

    def __init__(
        self,
        strategy: Strategy,
        executor: PaperExecutor,
        *,
        notifications: NotificationService | None = None,
        losing_trades: LosingTradeStore | None = None,
        checkpoint_store: PaperCheckpointStore | None = None,
        session_id: str | None = None,
        max_history: int = 1_000,
    ) -> None:
        if max_history <= 1:
            raise ValueError("max_history deve ser maior que um.")
        if (checkpoint_store is None) != (session_id is None):
            raise ValueError(
                "checkpoint_store e session_id devem ser definidos juntos."
            )
        self.strategy = strategy
        self.executor = executor
        self.notifications = notifications
        self.losing_trades = losing_trades
        self.checkpoint_store = checkpoint_store
        self.session_id = session_id
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
            self._save_checkpoint(())
            latest = self._history[-1]
            event = self._event(
                MonitoringEventType.SESSION_PRIMED,
                latest,
                f"Histórico aquecido com {len(self._history)} candles.",
            )
            return PaperTradingUpdate(
                primed_candles=len(self._history),
                monitoring_events=(event,),
            )

        new_candles = [
            candle
            for candle in candles
            if self._last_processed_open_time is None
            or candle.open_time > self._last_processed_open_time
        ]
        closed_trades: list[Trade] = []
        recorded_trades = 0
        recorded_losses = 0
        notification_results: list[NotificationResult] = []
        monitoring_events: list[MonitoringEvent] = []

        for candle in new_candles:
            self._append_history(candle)
            monitoring_events.append(
                self._event(
                    MonitoringEventType.CANDLE_PROCESSED,
                    candle,
                    "Candle processado.",
                )
            )
            before = self.executor.snapshot()
            trades = self.executor.process_candle(candle)
            after_execution = self.executor.snapshot()
            closed_trades.extend(trades)
            opened_position = after_execution.open_position
            opened_and_closed = (
                before.open_position is None
                and opened_position is None
                and bool(trades)
                and trades[0].opened_at == candle.open_time
            )
            if before.open_position is None and (
                opened_position is not None or opened_and_closed
            ):
                if opened_position is not None:
                    side = opened_position.side
                    entry_price = opened_position.entry_price
                else:
                    side = trades[0].side
                    entry_price = trades[0].entry_price
                monitoring_events.append(
                    self._event(
                        MonitoringEventType.POSITION_OPENED,
                        candle,
                        (
                            f"Posição virtual {self._side_label(side)} aberta "
                            f"em {entry_price}."
                        ),
                    )
                )
            elif (
                before.has_pending_signal
                and before.open_position is None
                and opened_position is None
                and not trades
            ):
                monitoring_events.append(
                    self._event(
                        MonitoringEventType.SIGNAL_REJECTED,
                        candle,
                        "Sinal rejeitado pelas regras de execução ou risco.",
                    )
                )
            for trade in trades:
                monitoring_events.append(
                    self._event(
                        MonitoringEventType.POSITION_CLOSED,
                        candle,
                        (
                            "Posição encerrada: "
                            f"{trade.net_pnl:+.2f} {self._quote_asset(trade.symbol)}."
                        ),
                    )
                )
            if self.losing_trades is not None:
                for trade in trades:
                    if self.losing_trades.save_loss(trade):
                        recorded_losses += 1
                        monitoring_events.append(
                            self._event(
                                MonitoringEventType.LOSS_RECORDED,
                                candle,
                                "Perda armazenada para aprendizado.",
                            )
                        )

            if (
                not self.executor.has_open_position
                and not self.executor.has_pending_signal
            ):
                signal = self.strategy.generate_signal(self._history)
                if self.executor.queue_signal(signal):
                    label = "COMPRA" if signal.action is SignalAction.BUY else "VENDA"
                    monitoring_events.append(
                        self._event(
                            MonitoringEventType.SIGNAL_FOUND,
                            candle,
                            f"Sinal de {label} encontrado.",
                        )
                    )
                else:
                    monitoring_events.append(
                        self._event(
                            MonitoringEventType.WAITING_SIGNAL,
                            candle,
                            f"Aguardando sinal: {signal.reason}",
                        )
                    )
            elif self.executor.has_open_position and not trades:
                monitoring_events.append(
                    self._event(
                        MonitoringEventType.POSITION_MONITORED,
                        candle,
                        "Posição aberta; aguardando stop ou alvo.",
                    )
                )
            self._last_processed_open_time = candle.open_time
            inserted = self._save_checkpoint(trades)
            recorded_trades += inserted
            for _ in range(inserted):
                monitoring_events.append(
                    self._event(
                        MonitoringEventType.TRADE_RECORDED,
                        candle,
                        "Operação registrada no histórico paper.",
                    )
                )

            if self.notifications is not None:
                for trade in trades:
                    results = self.notifications.notify_trade(trade)
                    notification_results.extend(results)
                    if any(result.success for result in results):
                        monitoring_events.append(
                            self._event(
                                MonitoringEventType.RESULT_NOTIFIED,
                                candle,
                                "Discord de resultados notificado.",
                            )
                        )
                    if any(not result.success for result in results):
                        monitoring_events.append(
                            self._event(
                                MonitoringEventType.RESULT_NOTIFICATION_FAILED,
                                candle,
                                "Falha ao notificar o Discord de resultados.",
                            )
                        )

        return PaperTradingUpdate(
            processed_candles=len(new_candles),
            closed_trades=tuple(closed_trades),
            recorded_trades=recorded_trades,
            recorded_losses=recorded_losses,
            notifications=tuple(notification_results),
            monitoring_events=tuple(monitoring_events),
        )

    def export_state(self) -> PaperTradingState:
        """Exporta todo o estado necessário para retomar a sessão."""

        return PaperTradingState(
            strategy_name=self.strategy.name,
            max_history=self.max_history,
            initialized=self._initialized,
            history=tuple(self._history),
            last_processed_open_time=self._last_processed_open_time,
            executor=self.executor.export_state(),
        )

    def restore_state(self, state: PaperTradingState) -> None:
        """Restaura um checkpoint compatível com esta instância."""

        if state.strategy_name != self.strategy.name:
            raise ValueError("O checkpoint pertence a outra estratégia.")
        if state.max_history != self.max_history:
            raise ValueError("O checkpoint usa outro tamanho de histórico.")
        self._validate_series(state.history)
        if state.initialized and (
            state.history[-1].open_time != state.last_processed_open_time
        ):
            raise ValueError("O cursor não corresponde ao último candle salvo.")
        if state.history:
            symbol = state.history[-1].symbol
            interval = state.history[-1].interval
            self._validate_executor_market(state, symbol, interval)
        self._history = list(state.history)
        self._last_processed_open_time = state.last_processed_open_time
        self._initialized = state.initialized
        self.executor.restore_state(state.executor)

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

    def _save_checkpoint(self, trades: Sequence[Trade]) -> int:
        if self.checkpoint_store is None or self.session_id is None:
            return 0
        return self.checkpoint_store.save_checkpoint(
            self.session_id,
            self.export_state(),
            trades,
        )

    @staticmethod
    def _validate_executor_market(
        state: PaperTradingState,
        symbol: str,
        interval: str,
    ) -> None:
        executor = state.executor
        candidates = (executor.pending_signal, executor.open_position)
        for candidate in candidates:
            if candidate is not None and (
                candidate.symbol != symbol or candidate.interval != interval
            ):
                raise ValueError(
                    "O estado do executor pertence a outra série de mercado."
                )

    @staticmethod
    def _event(
        event_type: MonitoringEventType,
        candle: Candle,
        message: str,
    ) -> MonitoringEvent:
        return MonitoringEvent(
            event_type=event_type,
            occurred_at=candle.close_time,
            symbol=candle.symbol,
            interval=candle.interval,
            message=message,
        )

    @staticmethod
    def _side_label(side: PositionSide) -> str:
        return "COMPRADA" if side is PositionSide.LONG else "VENDIDA"

    @staticmethod
    def _quote_asset(symbol: str) -> str:
        known_quotes = ("USDT", "USDC", "BUSD", "BTC", "ETH", "BRL")
        return next(
            (quote for quote in known_quotes if symbol.endswith(quote)),
            "unidades",
        )

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
