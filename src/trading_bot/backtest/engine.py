"""Motor cronológico de backtest sem antecipação de candles."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from trading_bot.backtest.config import BacktestConfig
from trading_bot.backtest.result import BacktestResult
from trading_bot.domain import (
    Candle,
    ExitReason,
    Position,
    Signal,
    SignalAction,
    Trade,
    TradeResult,
)
from trading_bot.execution import FillSimulator
from trading_bot.risk import RiskContext, RiskManager
from trading_bot.strategies import Strategy


class BacktestEngine:
    """Executa uma estratégia usando apenas informações disponíveis no tempo."""

    def __init__(
        self,
        strategy: Strategy,
        *,
        risk_manager: RiskManager | None = None,
        config: BacktestConfig | None = None,
    ) -> None:
        self.strategy = strategy
        self.risk_manager = risk_manager or RiskManager()
        self.config = config or BacktestConfig()
        self._fills = FillSimulator(
            fee_rate=self.config.fee_rate,
            slippage_rate=self.config.slippage_rate,
        )

    def run(self, candles: Sequence[Candle]) -> BacktestResult:
        """Simula sinais, entradas no candle seguinte e encerramentos."""

        self._validate_candles(candles)
        if not candles:
            return BacktestResult(
                initial_equity=self.config.initial_equity,
                final_equity=self.config.initial_equity,
                trades=(),
                equity_curve=(self.config.initial_equity,),
            )

        balance = self.config.initial_equity
        equity_curve = [balance]
        trades: list[Trade] = []
        pending_signal: Signal | None = None
        position: Position | None = None
        rejected_signals = 0
        trades_today = 0
        daily_net_pnl = Decimal(0)
        consecutive_losses = 0
        current_day: date | None = None
        day_start_equity = balance
        position_number = 0

        for index, candle in enumerate(candles):
            candle_day = candle.open_time.date()
            if candle_day != current_day:
                current_day = candle_day
                day_start_equity = balance
                daily_net_pnl = Decimal(0)
                trades_today = 0

            if pending_signal is not None and position is None:
                try:
                    executable_signal = self._fills.signal_at_open(
                        pending_signal,
                        candle,
                    )
                except ValueError:
                    rejected_signals += 1
                else:
                    context = RiskContext(
                        account_equity=balance,
                        day_start_equity=day_start_equity,
                        daily_net_pnl=daily_net_pnl,
                        trades_today=trades_today,
                        consecutive_losses=consecutive_losses,
                        open_positions=0,
                    )
                    assessment = self.risk_manager.evaluate(
                        executable_signal,
                        context,
                    )
                    if assessment.approved:
                        position_number += 1
                        trades_today += 1
                        position = self._fills.open_position(
                            executable_signal,
                            assessment.quantity,
                            candle,
                            f"position-{position_number}",
                        )
                    else:
                        rejected_signals += 1
                pending_signal = None

            if position is not None:
                exit_event = self._fills.exit_event(position, candle)
                if exit_event is not None:
                    exit_price, exit_reason = exit_event
                    trade = self._fills.close_position(
                        position,
                        candle,
                        exit_price,
                        exit_reason,
                        trade_id=position.position_id.replace("position", "trade"),
                    )
                    trades.append(trade)
                    balance += trade.net_pnl
                    if balance <= 0:
                        raise RuntimeError("O capital do backtest foi esgotado.")
                    daily_net_pnl += trade.net_pnl
                    equity_curve.append(balance)
                    if trade.result is TradeResult.LOSS:
                        consecutive_losses += 1
                    elif trade.result is TradeResult.WIN:
                        consecutive_losses = 0
                    position = None

            if position is None and pending_signal is None:
                signal = self.strategy.generate_signal(candles[: index + 1])
                if signal.action is not SignalAction.HOLD:
                    pending_signal = signal

        if position is not None:
            final_candle = candles[-1]
            trade = self._fills.close_position(
                position,
                final_candle,
                final_candle.close,
                ExitReason.END_OF_DATA,
                trade_id=position.position_id.replace("position", "trade"),
            )
            trades.append(trade)
            balance += trade.net_pnl
            if balance <= 0:
                raise RuntimeError("O capital do backtest foi esgotado.")
            equity_curve.append(balance)

        return BacktestResult(
            initial_equity=self.config.initial_equity,
            final_equity=balance,
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            rejected_signals=rejected_signals,
        )

    @staticmethod
    def _validate_candles(candles: Sequence[Candle]) -> None:
        if not candles:
            return
        first = candles[0]
        previous_open_time = first.open_time
        for candle in candles:
            if candle.symbol != first.symbol or candle.interval != first.interval:
                raise ValueError("Todos os candles devem pertencer à mesma série.")
        for candle in candles[1:]:
            if candle.open_time <= previous_open_time:
                raise ValueError("Candles devem estar em ordem cronológica.")
            previous_open_time = candle.open_time
