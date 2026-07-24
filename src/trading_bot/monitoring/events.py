"""Eventos observáveis produzidos pelo ciclo de paper trading."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MonitoringEventType(str, Enum):
    """Tipos estáveis usados pelo terminal e pelo Discord."""

    SESSION_PRIMED = "SESSION_PRIMED"
    SESSION_RESTORED = "SESSION_RESTORED"
    CANDLE_PROCESSED = "CANDLE_PROCESSED"
    WAITING_SIGNAL = "WAITING_SIGNAL"
    SIGNAL_FOUND = "SIGNAL_FOUND"
    SIGNAL_REJECTED = "SIGNAL_REJECTED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_MONITORED = "POSITION_MONITORED"
    POSITION_CLOSED = "POSITION_CLOSED"
    TRADE_RECORDED = "TRADE_RECORDED"
    LOSS_RECORDED = "LOSS_RECORDED"
    RESULT_NOTIFIED = "RESULT_NOTIFIED"
    RESULT_NOTIFICATION_FAILED = "RESULT_NOTIFICATION_FAILED"


@dataclass(frozen=True, slots=True)
class MonitoringEvent:
    """Uma linha de atividade sem qualquer segredo de configuração."""

    event_type: MonitoringEventType
    occurred_at: datetime
    symbol: str
    interval: str
    message: str

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at deve incluir fuso horário.")
        if not self.symbol or not self.interval or not self.message:
            raise ValueError("Símbolo, intervalo e mensagem são obrigatórios.")
