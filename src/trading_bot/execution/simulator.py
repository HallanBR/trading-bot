"""Regras compartilhadas de fill para backtest e paper trading."""

from decimal import Decimal

from trading_bot.domain import (
    Candle,
    ExitReason,
    Position,
    PositionSide,
    Signal,
    SignalAction,
    Trade,
)


class FillSimulator:
    """Simula entrada, slippage, taxas e saída sem acessar corretoras."""

    def __init__(
        self,
        *,
        fee_rate: Decimal,
        slippage_rate: Decimal,
    ) -> None:
        for name, value in {
            "fee_rate": fee_rate,
            "slippage_rate": slippage_rate,
        }.items():
            if not Decimal(0) <= value < Decimal(1):
                raise ValueError(f"{name} deve estar entre zero e um.")
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate

    def signal_at_open(self, signal: Signal, candle: Candle) -> Signal:
        """Reposiciona entrada, stop e alvo na abertura com slippage."""

        if signal.action is SignalAction.HOLD:
            raise ValueError("Sinais HOLD não podem ser executados.")
        assert signal.stop_loss is not None
        assert signal.take_profit is not None
        is_buy = signal.action is SignalAction.BUY
        entry_price = self.with_slippage(candle.open, is_buy=is_buy)
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
    def open_position(
        signal: Signal,
        quantity: Decimal,
        candle: Candle,
        position_id: str,
    ) -> Position:
        """Cria uma posição virtual a partir de um sinal aprovado."""

        if signal.action is SignalAction.HOLD:
            raise ValueError("Sinais HOLD não podem abrir posições.")
        assert signal.stop_loss is not None
        assert signal.take_profit is not None
        side = (
            PositionSide.LONG
            if signal.action is SignalAction.BUY
            else PositionSide.SHORT
        )
        return Position(
            position_id=position_id,
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

    @staticmethod
    def exit_event(
        position: Position,
        candle: Candle,
    ) -> tuple[Decimal, ExitReason] | None:
        """Detecta stop ou alvo, priorizando o stop em candles ambíguos."""

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

    def close_position(
        self,
        position: Position,
        candle: Candle,
        raw_exit_price: Decimal,
        reason: ExitReason,
        *,
        trade_id: str,
    ) -> Trade:
        """Fecha uma posição virtual aplicando slippage e taxas dos dois fills."""

        exit_is_buy = position.side is PositionSide.SHORT
        exit_price = self.with_slippage(raw_exit_price, is_buy=exit_is_buy)
        entry_fee = position.entry_price * position.quantity * self.fee_rate
        exit_fee = exit_price * position.quantity * self.fee_rate
        return Trade(
            trade_id=trade_id,
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

    def with_slippage(self, price: Decimal, *, is_buy: bool) -> Decimal:
        """Piora o preço na direção esperada de uma ordem simulada."""

        direction = Decimal(1) if is_buy else Decimal(-1)
        return price * (Decimal(1) + (direction * self.slippage_rate))
