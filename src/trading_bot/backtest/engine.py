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
    PositionSide,
    Signal,
    SignalAction,
    Trade,
    TradeResult,
)
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
                    executable_signal = self._signal_at_open(pending_signal, candle)
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
                        position = self._open_position(
                            executable_signal,
                            assessment.quantity,
                            candle,
                            position_number,
                        )
                    else:
                        rejected_signals += 1
                pending_signal = None

            if position is not None:
                exit_event = self._exit_event(position, candle)
                if exit_event is not None:
                    exit_price, exit_reason = exit_event
                    trade = self._close_position(
                        position,
                        candle,
                        exit_price,
                        exit_reason,
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
            trade = self._close_position(
                position,
                final_candle,
                final_candle.close,
                ExitReason.END_OF_DATA,
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

    def _signal_at_open(self, signal: Signal, candle: Candle) -> Signal:
        assert signal.stop_loss is not None
        assert signal.take_profit is not None
        is_buy = signal.action is SignalAction.BUY
        entry_price = self._with_slippage(candle.open, is_buy=is_buy)
        stop_distance = abs(signal.price - signal.stop_loss)
        target_distance = abs(signal.take_profit - signal.price)

        if is_buy:
            stop_loss = entry_price - stop_distance
            take_profit = entry_price + target_distance
        else:
            stop_loss = entry_price + stop_distance
            take_profit = entry_price - target_distance

        return Signal(
            symbol=signal.symbol,
            interval=signal.interval,
            action=signal.action,
            generated_at=signal.generated_at,
            price=entry_price,
            strategy=signal.strategy,
            reason=signal.reason,
            stop_loss=stop_loss,
            take_profit=take_profit,
            indicators=signal.indicators,
        )

    @staticmethod
    def _open_position(
        signal: Signal,
        quantity: Decimal,
        candle: Candle,
        position_number: int,
    ) -> Position:
        assert signal.stop_loss is not None
        assert signal.take_profit is not None
        side = (
            PositionSide.LONG
            if signal.action is SignalAction.BUY
            else PositionSide.SHORT
        )
        return Position(
            position_id=f"position-{position_number}",
            symbol=signal.symbol,
            interval=signal.interval,
            side=side,
            quantity=quantity,
            entry_price=signal.price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            opened_at=candle.open_time,
            strategy=signal.strategy,
        )

    def _exit_event(
        self,
        position: Position,
        candle: Candle,
    ) -> tuple[Decimal, ExitReason] | None:
        if position.side is PositionSide.LONG:
            if candle.open <= position.stop_loss:
                return candle.open, ExitReason.STOP_LOSS
            if candle.open >= position.take_profit:
                return candle.open, ExitReason.TAKE_PROFIT
            if candle.low <= position.stop_loss:
                return position.stop_loss, ExitReason.STOP_LOSS
            if candle.high >= position.take_profit:
                return position.take_profit, ExitReason.TAKE_PROFIT
        else:
            if candle.open >= position.stop_loss:
                return candle.open, ExitReason.STOP_LOSS
            if candle.open <= position.take_profit:
                return candle.open, ExitReason.TAKE_PROFIT
            if candle.high >= position.stop_loss:
                return position.stop_loss, ExitReason.STOP_LOSS
            if candle.low <= position.take_profit:
                return position.take_profit, ExitReason.TAKE_PROFIT
        return None

    def _close_position(
        self,
        position: Position,
        candle: Candle,
        raw_exit_price: Decimal,
        reason: ExitReason,
    ) -> Trade:
        exit_is_buy = position.side is PositionSide.SHORT
        exit_price = self._with_slippage(raw_exit_price, is_buy=exit_is_buy)
        entry_fee = position.entry_price * position.quantity * self.config.fee_rate
        exit_fee = exit_price * position.quantity * self.config.fee_rate
        return Trade(
            trade_id=position.position_id.replace("position", "trade"),
            symbol=position.symbol,
            interval=position.interval,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=exit_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            fees=entry_fee + exit_fee,
            opened_at=position.opened_at,
            closed_at=candle.close_time,
            strategy=position.strategy,
            exit_reason=reason,
        )

    def _with_slippage(self, price: Decimal, *, is_buy: bool) -> Decimal:
        direction = Decimal(1) if is_buy else Decimal(-1)
        return price * (Decimal(1) + (direction * self.config.slippage_rate))

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
