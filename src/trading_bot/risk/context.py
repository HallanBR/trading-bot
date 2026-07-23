"""Estado da conta necessário para avaliar um novo sinal."""

from dataclasses import dataclass
from decimal import Decimal

from trading_bot.domain._validation import require_positive


@dataclass(frozen=True, slots=True)
class RiskContext:
    """Resumo imutável do risco corrente da conta simulada."""

    account_equity: Decimal
    day_start_equity: Decimal
    daily_net_pnl: Decimal = Decimal(0)
    trades_today: int = 0
    consecutive_losses: int = 0
    open_positions: int = 0

    def __post_init__(self) -> None:
        require_positive(self.account_equity, "account_equity")
        require_positive(self.day_start_equity, "day_start_equity")
        counts = {
            "trades_today": self.trades_today,
            "consecutive_losses": self.consecutive_losses,
            "open_positions": self.open_positions,
        }
        for name, value in counts.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} deve ser um inteiro não negativo.")
