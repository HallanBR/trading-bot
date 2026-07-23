"""Orquestração resiliente de canais de notificação."""

from dataclasses import dataclass

from trading_bot.domain import Trade
from trading_bot.notifications.base import TradeNotifier
from trading_bot.notifications.exceptions import NotificationError


@dataclass(frozen=True, slots=True)
class NotificationResult:
    """Resultado do envio para um canal, sem interromper outros canais."""

    channel: str
    success: bool
    error: str | None = None


class NotificationService:
    """Distribui um trade encerrado e isola falhas de cada canal."""

    def __init__(self, notifiers: list[TradeNotifier]) -> None:
        self._notifiers = tuple(notifiers)

    def notify_trade(self, trade: Trade) -> tuple[NotificationResult, ...]:
        """Tenta todos os canais e retorna resultados observáveis."""

        results: list[NotificationResult] = []
        for notifier in self._notifiers:
            try:
                notifier.notify_trade(trade)
            except NotificationError as exc:
                results.append(
                    NotificationResult(
                        channel=notifier.name,
                        success=False,
                        error=str(exc),
                    )
                )
            else:
                results.append(
                    NotificationResult(
                        channel=notifier.name,
                        success=True,
                    )
                )
        return tuple(results)
