"""Executor stateful para operações totalmente virtuais."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from trading_bot.domain import (
    Candle,
    Position,
    Signal,
    SignalAction,
    Trade,
    TradeResult,
)
from trading_bot.execution.simulator import FillSimulator
from trading_bot.risk import RiskContext, RiskManager


@dataclass(frozen=True, slots=True)
class PaperAccountSnapshot:
    """Estado observável da conta simulada."""

    equity: Decimal
    open_position: Position | None
    has_pending_signal: bool
    trades_today: int
    daily_net_pnl: Decimal
    consecutive_losses: int
    rejected_signals: int


@dataclass(frozen=True, slots=True)
class PaperExecutorState:
    """Estado completo necessário para continuar uma conta paper."""

    equity: Decimal
    pending_signal: Signal | None
    open_position: Position | None
    current_day: date | None
    day_start_equity: Decimal
    daily_net_pnl: Decimal
    trades_today: int
    consecutive_losses: int
    rejected_signals: int
    position_number: int

    def __post_init__(self) -> None:
        if self.equity <= 0 or self.day_start_equity <= 0:
            raise ValueError("Os valores de capital do estado devem ser positivos.")
        counters = (
            self.trades_today,
            self.consecutive_losses,
            self.rejected_signals,
            self.position_number,
        )
        if any(
            isinstance(counter, bool) or not isinstance(counter, int) or counter < 0
            for counter in counters
        ):
            raise ValueError("Contadores do estado devem ser inteiros não negativos.")
        if self.pending_signal is not None and self.open_position is not None:
            raise ValueError("O estado não pode ter sinal e posição simultaneamente.")
        if self.open_position is not None and self.position_number == 0:
            raise ValueError("Uma posição aberta exige um contador de posições.")


class PaperExecutor:
    """Mantém uma conta virtual e processa um candle fechado por vez."""

    def __init__(
        self,
        *,
        initial_equity: Decimal,
        risk_manager: RiskManager,
        fills: FillSimulator,
    ) -> None:
        if initial_equity <= 0:
            raise ValueError("initial_equity deve ser positivo.")
        self._equity = initial_equity
        self._risk_manager = risk_manager
        self._fills = fills
        self._pending_signal: Signal | None = None
        self._position: Position | None = None
        self._current_day: date | None = None
        self._day_start_equity = initial_equity
        self._daily_net_pnl = Decimal(0)
        self._trades_today = 0
        self._consecutive_losses = 0
        self._rejected_signals = 0
        self._position_number = 0

    @property
    def has_open_position(self) -> bool:
        return self._position is not None

    @property
    def has_pending_signal(self) -> bool:
        return self._pending_signal is not None

    def queue_signal(self, signal: Signal) -> bool:
        """Agenda um sinal para a abertura do próximo candle."""

        if signal.action is SignalAction.HOLD:
            return False
        if self._position is not None or self._pending_signal is not None:
            return False
        self._pending_signal = signal
        return True

    def process_candle(self, candle: Candle) -> tuple[Trade, ...]:
        """Executa sinal pendente e monitora a posição no candle recebido."""

        self._reset_day_if_needed(candle)
        closed_trades: list[Trade] = []

        if self._pending_signal is not None and self._position is None:
            try:
                executable_signal = self._fills.signal_at_open(
                    self._pending_signal,
                    candle,
                )
            except ValueError:
                self._rejected_signals += 1
            else:
                assessment = self._risk_manager.evaluate(
                    executable_signal,
                    self._risk_context(),
                )
                if assessment.approved:
                    self._position_number += 1
                    self._trades_today += 1
                    self._position = self._fills.open_position(
                        executable_signal,
                        assessment.quantity,
                        candle,
                        f"paper-position-{self._position_number}",
                    )
                else:
                    self._rejected_signals += 1
            self._pending_signal = None

        if self._position is not None:
            exit_event = self._fills.exit_event(self._position, candle)
            if exit_event is not None:
                raw_exit_price, reason = exit_event
                trade = self._fills.close_position(
                    self._position,
                    candle,
                    raw_exit_price,
                    reason,
                    trade_id=f"paper-trade-{self._position_number}",
                )
                self._apply_trade(trade)
                self._position = None
                closed_trades.append(trade)

        return tuple(closed_trades)

    def snapshot(self) -> PaperAccountSnapshot:
        """Retorna o estado atual sem permitir mutação externa."""

        return PaperAccountSnapshot(
            equity=self._equity,
            open_position=self._position,
            has_pending_signal=self._pending_signal is not None,
            trades_today=self._trades_today,
            daily_net_pnl=self._daily_net_pnl,
            consecutive_losses=self._consecutive_losses,
            rejected_signals=self._rejected_signals,
        )

    def export_state(self) -> PaperExecutorState:
        """Exporta uma cópia imutável de todo o estado interno."""

        return PaperExecutorState(
            equity=self._equity,
            pending_signal=self._pending_signal,
            open_position=self._position,
            current_day=self._current_day,
            day_start_equity=self._day_start_equity,
            daily_net_pnl=self._daily_net_pnl,
            trades_today=self._trades_today,
            consecutive_losses=self._consecutive_losses,
            rejected_signals=self._rejected_signals,
            position_number=self._position_number,
        )

    def restore_state(self, state: PaperExecutorState) -> None:
        """Restaura um checkpoint validado sem modificar risco ou fills."""

        self._equity = state.equity
        self._pending_signal = state.pending_signal
        self._position = state.open_position
        self._current_day = state.current_day
        self._day_start_equity = state.day_start_equity
        self._daily_net_pnl = state.daily_net_pnl
        self._trades_today = state.trades_today
        self._consecutive_losses = state.consecutive_losses
        self._rejected_signals = state.rejected_signals
        self._position_number = state.position_number

    def _risk_context(self) -> RiskContext:
        return RiskContext(
            account_equity=self._equity,
            day_start_equity=self._day_start_equity,
            daily_net_pnl=self._daily_net_pnl,
            trades_today=self._trades_today,
            consecutive_losses=self._consecutive_losses,
            open_positions=int(self._position is not None),
        )

    def _reset_day_if_needed(self, candle: Candle) -> None:
        candle_day = candle.open_time.date()
        if candle_day != self._current_day:
            self._current_day = candle_day
            self._day_start_equity = self._equity
            self._daily_net_pnl = Decimal(0)
            self._trades_today = 0

    def _apply_trade(self, trade: Trade) -> None:
        self._equity += trade.net_pnl
        if self._equity <= 0:
            raise RuntimeError("O capital da conta paper foi esgotado.")
        self._daily_net_pnl += trade.net_pnl
        if trade.result is TradeResult.LOSS:
            self._consecutive_losses += 1
        elif trade.result is TradeResult.WIN:
            self._consecutive_losses = 0
