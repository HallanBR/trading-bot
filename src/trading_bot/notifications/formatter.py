"""Formatação de trades como embeds do Discord."""

from decimal import Decimal
from typing import Any

from trading_bot.domain import ExitReason, PositionSide, Trade, TradeResult

GREEN = 0x2ECC71
RED = 0xE74C3C
GRAY = 0x95A5A6


class DiscordTradeFormatter:
    """Cria uma mensagem curta sem incluir dados de conta ou credenciais."""

    def format(self, trade: Trade) -> dict[str, Any]:
        """Converte um trade encerrado em payload aceito por webhooks."""

        title, color = self._appearance(trade.result)
        direction = (
            "Compra (LONG)" if trade.side is PositionSide.LONG else "Venda (SHORT)"
        )
        return {
            "username": "Trading Bot",
            "allowed_mentions": {"parse": []},
            "embeds": [
                {
                    "title": title,
                    "color": color,
                    "fields": [
                        {
                            "name": "Ativo",
                            "value": f"`{trade.symbol}` · `{trade.interval}`",
                            "inline": True,
                        },
                        {
                            "name": "Direção",
                            "value": direction,
                            "inline": True,
                        },
                        {
                            "name": "Entrada → saída",
                            "value": (
                                f"`{self._decimal(trade.entry_price)}` → "
                                f"`{self._decimal(trade.exit_price)}`"
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Resultado líquido",
                            "value": (
                                f"`{self._signed(trade.net_pnl)}` "
                                f"(`{self._signed(self._return_percent(trade))}%`)"
                            ),
                            "inline": True,
                        },
                        {
                            "name": "Taxas",
                            "value": f"`{self._decimal(trade.fees)}`",
                            "inline": True,
                        },
                        {
                            "name": "Encerramento",
                            "value": self._exit_reason(trade.exit_reason),
                            "inline": True,
                        },
                    ],
                    "footer": {"text": f"Estratégia: {trade.strategy}"},
                    "timestamp": trade.closed_at.isoformat(),
                }
            ],
        }

    @staticmethod
    def _appearance(result: TradeResult) -> tuple[str, int]:
        if result is TradeResult.WIN:
            return "🟢 Operação vitoriosa", GREEN
        if result is TradeResult.LOSS:
            return "🔴 Operação perdedora", RED
        return "⚪ Operação encerrada no zero", GRAY

    @staticmethod
    def _decimal(value: Decimal) -> str:
        rendered = format(value, "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        return rendered or "0"

    @classmethod
    def _signed(cls, value: Decimal) -> str:
        rendered = cls._decimal(value)
        return f"+{rendered}" if value > 0 else rendered

    @staticmethod
    def _return_percent(trade: Trade) -> Decimal:
        entry_notional = trade.entry_price * trade.quantity
        return (trade.net_pnl / entry_notional) * Decimal(100)

    @staticmethod
    def _exit_reason(reason: ExitReason) -> str:
        return {
            ExitReason.TAKE_PROFIT: "Take-profit",
            ExitReason.STOP_LOSS: "Stop-loss",
            ExitReason.STRATEGY: "Sinal da estratégia",
            ExitReason.MANUAL: "Encerramento manual",
            ExitReason.END_OF_DATA: "Fim dos dados",
        }[reason]
