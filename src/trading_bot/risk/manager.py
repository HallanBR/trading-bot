"""Aplicação centralizada dos limites de risco."""

from trading_bot.domain import Signal, SignalAction
from trading_bot.risk.assessment import RiskAssessment
from trading_bot.risk.config import RiskConfig
from trading_bot.risk.context import RiskContext
from trading_bot.risk.position_sizing import calculate_position_size


class RiskManager:
    """Decide se um sinal pode se tornar uma posição simulada."""

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()

    def evaluate(self, signal: Signal, context: RiskContext) -> RiskAssessment:
        """Avalia limites globais, relação risco/retorno e tamanho da posição."""

        rejection = self._global_rejection(signal, context)
        if rejection is not None:
            return RiskAssessment(approved=False, reason=rejection)

        assert signal.stop_loss is not None
        assert signal.take_profit is not None
        risk_distance = abs(signal.price - signal.stop_loss)
        reward_distance = abs(signal.take_profit - signal.price)
        risk_reward = reward_distance / risk_distance
        if risk_reward < self.config.min_risk_reward:
            return RiskAssessment(
                approved=False,
                reason=(
                    "Relação risco/retorno abaixo do mínimo "
                    f"de {self.config.min_risk_reward}."
                ),
            )

        size = calculate_position_size(
            signal,
            account_equity=context.account_equity,
            risk_fraction=self.config.risk_per_trade,
            max_position_fraction=self.config.max_position_fraction,
            max_position_notional=self.config.max_position_notional,
        )
        return RiskAssessment(
            approved=True,
            reason="Sinal aprovado pelos limites de risco.",
            quantity=size.quantity,
            risk_amount=size.risk_amount,
            notional=size.notional,
            risk_reward_ratio=risk_reward,
        )

    def _global_rejection(
        self,
        signal: Signal,
        context: RiskContext,
    ) -> str | None:
        if signal.action is SignalAction.HOLD:
            return "Sinais HOLD não abrem posições."

        daily_loss_limit = context.day_start_equity * self.config.max_daily_loss
        if context.daily_net_pnl <= -daily_loss_limit:
            return "Limite de perda diária atingido."
        if context.trades_today >= self.config.max_trades_per_day:
            return "Limite diário de operações atingido."
        if context.consecutive_losses >= self.config.max_consecutive_losses:
            return "Limite de perdas consecutivas atingido."
        if context.open_positions >= self.config.max_open_positions:
            return "Limite de posições simultâneas atingido."
        return None
